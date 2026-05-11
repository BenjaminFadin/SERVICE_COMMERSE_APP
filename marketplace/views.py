import io
from datetime import datetime
from django.http import HttpResponse
from django.db.models import Q, Exists, OuterRef, Prefetch
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.conf import settings
from django.core.mail import send_mail

from .forms import BookingForm, BusinessLeadForm
from .models import Appointment, Category, Master, Salon, Service
from .utils import get_available_slots, send_telegram_message, can_book_pc_quantity


def search_view(request):
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    
    # Start with all active salons (or masters)
    results = Salon.objects.all()

    if query:
        # Creative part: Search across multiple related models
        results = results.filter(
            Q(name_ru__icontains=query) | 
            Q(category__name_ru__icontains=query) | 
            Q(services__name_ru__icontains=query) |
            Q(description_ru__icontains=query)
        ).distinct()

    if location:
        results = results.filter(address__icontains=location)

    return render(request, 'search_results.html', {'results': results, 'query': query})

def _salon_is_pc_club(salon):
    """Detect PC clubs by category slug (fast, no DB column needed)."""
    PC_CLUB_SLUGS = {
        "pc-club", "pc-clubs", "computer-club", "pc",
        "kompyuter-klub", "obychnye-pk",
    }
    cat = getattr(salon, "category", None)
    while cat is not None:
        if cat.slug in PC_CLUB_SLUGS:
            return True
        cat = cat.parent
    return False

def home(request):
    categories = Category.objects.filter(parent__isnull=True)
    return render(request, "marketplace/category_list.html", {"categories": categories})


def salon_list(request, category_slug=None):
    query = (request.GET.get("q") or "").strip()
    location = (request.GET.get("location") or "").strip()

    category = None
    subcategories = None

    salons_qs = (
        Salon.objects
        .select_related("category", "owner")
        .order_by("-created_at")
    )

    # Category filter (MPTT)
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        categories_to_include = category.get_descendants(include_self=True)

        salons_qs = salons_qs.filter(category__in=categories_to_include)

        if category.is_leaf_node() and category.parent_id:
            subcategories = category.parent.get_children()
        else:
            subcategories = category.get_children()

    if not subcategories:
        subcategories = Category.objects.filter(level=0).only(
            "id", "slug", "name_ru", "name_en", "name_uz", "icon_class", "parent_id", "level"
        )

    # Search (NO JOIN on services => no duplicates => no DISTINCT)
    if query:
        service_match = Service.objects.filter(
            salon_id=OuterRef("pk"),
        ).filter(
            Q(name_ru__icontains=query) |
            Q(name_en__icontains=query) |
            Q(name_uz__icontains=query)
        )

        salons_qs = salons_qs.filter(
            Q(name__icontains=query) |                       # <-- Salon has only "name"
            Q(category__name_ru__icontains=query) |
            Q(category__name_en__icontains=query) |
            Q(category__name_uz__icontains=query) |
            Exists(service_match)
        )

    if location:
        salons_qs = salons_qs.filter(address__icontains=location)

    # Prefetch only if template actually needs services (otherwise remove this block)
    salons_qs = salons_qs.prefetch_related(
        Prefetch(
            "services",
            queryset=Service.objects.only("id", "salon_id", "name_ru", "name_en", "name_uz", "price", "duration_minutes", "img"),
        )
    )

    paginator = Paginator(salons_qs, 10)
    salons_page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "marketplace/salon_list.html",
        {
            "salons": salons_page,
            "category": category,
            "subcategories": subcategories,
            "search_query": query,
            "search_location": location,
        },
    )

def salon_detail(request, salon_id):
    # Optimized query with select_related and prefetch_related
    salon = get_object_or_404(
        Salon.objects.select_related("category").prefetch_related("photos", "services", "masters", "working_hours"), 
        pk=salon_id
    )
    
    services = salon.services.all()
    masters = salon.masters.filter(is_active=True)
    photos = salon.photos.all()
    
    # Get working hours ordered by weekday (Monday=0, Sunday=6)
    working_hours = salon.working_hours.all().order_by('weekday')
    
    return render(
        request,
        "marketplace/salon_detail.html",
        {
            "salon": salon, 
            "services": services, 
            "masters": masters,
            "photos": photos,
            "working_hours": working_hours,
            "today_weekday": timezone.localtime().weekday() # Returns 0-6
        },
    )

@login_required
def booking_start(request, salon_id, service_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    service = get_object_or_404(Service, pk=service_id, salon=salon)
    is_pc_club = _salon_is_pc_club(salon)

    if request.method == "POST":
        form = BookingForm(request.POST, salon=salon, is_pc_club=is_pc_club)
        if form.is_valid():
            start_dt = form.build_start_datetime()
            quantity = form.cleaned_data.get("quantity") or 1
            
            if is_pc_club:
                ok, available = can_book_pc_quantity(salon, service, start_dt, quantity)
                if not ok:
                    form.add_error(None, f"Only {available} PC(s) available at this time.")
                else:
                    Appointment.objects.create(
                        client=request.user,
                        salon=salon,
                        master=None,
                        service=service,
                        start_time=start_dt,
                        status="pending",
                        comment=form.cleaned_data.get("comment", ""),
                        quantity=quantity
                    )
                    return redirect("marketplace:booking_success", salon_id=salon.id)
            else:
                master = form.cleaned_data["master"]
                slots = get_available_slots(
                    salon=salon,
                    master=master,
                    service=service,
                    date_obj=form.cleaned_data["date"],
                )
                if start_dt not in slots:
                    form.add_error(None, "Selected time is no longer available.")
                else:
                    Appointment.objects.create(
                        client=request.user,
                        salon=salon,
                        master=master,
                        service=service,
                        start_time=start_dt,
                        status="pending",
                        comment=form.cleaned_data.get("comment", ""),
                        quantity=1
                    )
                    return redirect("marketplace:booking_success", salon_id=salon.id)
    else:
        initial = {"date": timezone.localdate()}
        if is_pc_club:
            try:
                initial["quantity"] = int(request.GET.get("quantity", 1))
            except (TypeError, ValueError):
                initial["quantity"] = 1
        form = BookingForm(salon=salon, is_pc_club=is_pc_club, initial=initial)

    return render(
        request,
        "marketplace/booking_start.html",
        {"salon": salon, "service": service, "form": form, "is_pc_club": is_pc_club},
    )

@login_required
def booking_success(request, salon_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    return render(request, "marketplace/booking_success.html", {"salon": salon})

@login_required
def owner_dashboard(request):
    # Get all salons owned by this user
    salons = request.user.salons.all()

    # Check if the user is a Master (via the profile relation you created earlier)
    master_profile = getattr(request.user, 'master_profile', None)

    # If not a salon owner and not a master, they shouldn't be here
    if not salons.exists() and not master_profile:
        return render(request, "business/dashboard.html", {"salon": None, "bookings_today": []})

    today = timezone.localdate()

    # Base Queryset: Select salon or master context
    if salons.exists():
        target_salon = salons.first()
        base_query = Appointment.objects.filter(salon=target_salon)
    else:
        target_salon = master_profile.salon
        base_query = Appointment.objects.filter(master=master_profile)

    # NEW: Pending bookings — provider must accept/decline
    bookings_pending = base_query.filter(status="pending").select_related(
        "client", "client__profile", "service", "master"
    ).order_by("start_time")

    # Fetching split datasets for the UI
    bookings_today = base_query.filter(start_time__date=today).select_related("client", "service", "master").order_by('start_time')

    bookings_upcoming = base_query.filter(start_time__date__gt=today).select_related("client", "service", "master").order_by('start_time')

    bookings_past = base_query.filter(start_time__date__lt=today).select_related("client", "service", "master").order_by('-start_time')

    return render(request, "business/dashboard.html", {
        "salon": target_salon,
        "bookings_pending": bookings_pending,   # <-- NEW
        "bookings_today": bookings_today,
        "bookings_upcoming": bookings_upcoming,
        "bookings_past": bookings_past,
        "today": today
    })
    

@login_required
@require_POST
def accept_booking(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("client__profile", "salon", "service", "master"),
        pk=appointment_id,
    )

    if not _user_can_manage_appointment(request.user, appointment):
        messages.error(request, "You are not allowed to manage this booking.")
        return redirect("marketplace:owner_dashboard")

    if appointment.status != "pending":
        messages.warning(request, "This booking has already been processed.")
        return redirect("marketplace:owner_dashboard")

    appointment.status = "confirmed"
    appointment.save(update_fields=["status"])
    _notify_client_status_change(appointment, action="accepted")

    messages.success(request, "Booking accepted. The client has been notified.")
    return redirect("marketplace:owner_dashboard")


@login_required
@require_POST
def decline_booking(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related("client__profile", "salon", "service", "master"),
        pk=appointment_id,
    )

    if not _user_can_manage_appointment(request.user, appointment):
        messages.error(request, "You are not allowed to manage this booking.")
        return redirect("marketplace:owner_dashboard")

    if appointment.status != "pending":
        messages.warning(request, "This booking has already been processed.")
        return redirect("marketplace:owner_dashboard")

    appointment.status = "cancelled"
    appointment.save(update_fields=["status"])
    _notify_client_status_change(appointment, action="declined")

    messages.success(request, "Booking declined. The client has been notified.")
    return redirect("marketplace:owner_dashboard")

def _notify_client_status_change(appointment, action):
    """
    Send a Telegram message to the CLIENT when the provider
    accepts or declines their booking.
    action: "accepted" or "declined"
    """
    client_profile = getattr(appointment.client, "profile", None)
    if not client_profile or not client_profile.telegram_id:
        return

    service_name = appointment.service.name_ru if appointment.service else "-"
    master_name = appointment.master.name if appointment.master else "-"
    start_time = timezone.localtime(appointment.start_time).strftime("%d.%m.%Y %H:%M")

    if action == "accepted":
        text = (
            "<b>✅ Booking Accepted</b>\n\n"
            f"Your booking at <b>{appointment.salon.name}</b> has been confirmed.\n\n"
            f"Service: {service_name}\n"
            f"Master: {master_name}\n"
            f"Time: {start_time}\n\n"
            "See you soon!"
        )
    else:  # declined
        text = (
            "<b>❌ Booking Declined</b>\n\n"
            f"Unfortunately, <b>{appointment.salon.name}</b> had to decline your booking.\n\n"
            f"Service: {service_name}\n"
            f"Master: {master_name}\n"
            f"Time: {start_time}\n\n"
            "You can choose another time or another salon."
        )

    send_telegram_message(client_profile.telegram_id, text)

def _user_can_manage_appointment(user, appointment):
    """
    Salon owner OR the assigned master can manage (accept/decline) bookings.
    """
    if appointment.salon.owner_id == user.id:
        return True
    master_profile = getattr(user, "master_profile", None)
    if master_profile and appointment.master_id == master_profile.id:
        return True
    return False


@require_GET
def ajax_booking_form(request, salon_id, service_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    service = get_object_or_404(Service, pk=service_id, salon=salon)

    form = BookingForm(salon=salon, initial={"date": timezone.localdate()})
    form.fields["master"].queryset = Master.objects.filter(salon=salon, is_active=True)

    return render(
        request,
        "marketplace/partials/booking_form_inner.html",
        {"salon": salon, "service": service, "form": form},
    )


@require_GET
def api_slots(request, salon_id, service_id):
    salon = get_object_or_404(Salon, pk=salon_id)
    service = get_object_or_404(Service, pk=service_id, salon=salon)

    master_id = request.GET.get("master") or request.GET.get("master_id")
    date_str = request.GET.get("date") or request.GET.get("day")

    # Useful for debugging from browser DevTools Network tab
    if not master_id or not date_str:
        return JsonResponse(
            {"slots": [], "error": "missing master/date", "got": {"master": master_id, "date": date_str}},
            status=400,
        )

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": [], "error": "bad date format, expected YYYY-MM-DD"}, status=400)

    # Ensure master exists and belongs to salon
    master = salon.masters.filter(pk=master_id, is_active=True).first()
    if not master:
        return JsonResponse({"slots": [], "error": "master not found for this salon"}, status=404)

    try:
        slots = get_available_slots(salon=salon, master=master, service=service, date_obj=date_obj)
    except Exception as e:
        # So you see errors instead of silent empty behavior
        return JsonResponse({"slots": [], "error": f"server error: {str(e)}"}, status=500)

    # Make sure all datetimes are aware before localtime()
    out = []
    tz = timezone.get_current_timezone()
    for s in slots:
        if timezone.is_naive(s):
            s = timezone.make_aware(s, tz)
        out.append(timezone.localtime(s, tz).strftime("%H:%M"))

    return JsonResponse(
        {
            "slots": out,
            "meta": {
                "count": len(out),
                "date": date_str,
                "weekday": date_obj.weekday(),
                "salon_id": salon_id,
                "service_id": service_id,
                "master_id": int(master_id),
            },
        }
    )


@login_required
def my_bookings(request):
    now = timezone.now()
    bookings = Appointment.objects.filter(client=request.user).select_related('salon', 'service', 'master', 'plan')

    # Upcoming = anything not yet past AND not cancelled/completed
    upcoming_bookings = bookings.filter(
        start_time__gte=now,
    ).exclude(status__in=["cancelled", "completed"]).order_by('start_time')

    past_bookings = bookings.filter(
        start_time__lt=now
    ).order_by('-start_time')

    return render(request, 'marketplace/my_bookings.html', {
        'upcoming': upcoming_bookings,
        'past': past_bookings,
    })

@login_required
@require_POST
def cancel_booking(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id, client=request.user)
    
    # Only allow cancellation if it's pending or confirmed
    if appointment.status in ['pending', 'confirmed']:
        appointment.status = 'cancelled'
        appointment.save()
        messages.success(request, "Your booking has been cancelled.")
    else:
        messages.error(request, "This booking cannot be cancelled.")
        
    return redirect('marketplace:my_bookings')


@require_POST
def submit_business_lead(request):
    """Handle 'Add Business' popup form. Saves lead + sends Telegram notification."""
    form = BusinessLeadForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    lead = form.save()

    # Send Telegram notification to admin
    chat_id = getattr(settings, "BUSINESS_LEADS_TELEGRAM_ID", None)
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)

    print("=" * 60)
    print(f"[LEAD #{lead.pk}] Sending Telegram notification...")
    print(f"  chat_id   = {chat_id!r}")
    print(f"  bot_token = {'SET (' + str(len(bot_token)) + ' chars)' if bot_token else 'MISSING'}")

    if not chat_id:
        print(f"[LEAD #{lead.pk}] BUSINESS_LEADS_TELEGRAM_ID is not set in .env")
    elif not bot_token:
        print(f"[LEAD #{lead.pk}] TELEGRAM_BOT_TOKEN is not set in .env")
    else:
        try:
            text = (
                "<b>🆕 Новая заявка на добавление бизнеса</b>\n\n"
                f"📞 <b>Телефон:</b> {lead.phone}\n"
                f"📝 <b>Описание:</b>\n{lead.description}\n\n"
                f"🕒 {lead.created_at:%Y-%m-%d %H:%M}\n"
                f"🆔 ID: {lead.pk}"
            )
            ok = send_telegram_message(str(chat_id), text)
            print(f"[LEAD #{lead.pk}] send_telegram_message returned: {ok}")
        except Exception as e:
            print(f"[LEAD #{lead.pk}] Exception: {e}")

    print("=" * 60)

    return JsonResponse({
        "ok": True,
        "message": "Спасибо! Мы свяжемся с вами в ближайшее время.",
    })


# QR SIDE
def qr_checkout(request, salon_id, token):
    """
    Customer scans QR → most recent pending/confirmed booking at this salon
    is auto-completed.
    """
    salon = get_object_or_404(Salon, pk=salon_id, qr_token=token)

    if not request.user.is_authenticated:
        # Redirect to login, then back here
        login_url = "/accounts/auth/?next=" + request.path
        return redirect(login_url)

    # Find most recent active booking at this salon for this user
    appt = (
        Appointment.objects
        .filter(client=request.user, salon=salon, status__in=["pending", "confirmed"])
        .order_by("-start_time")
        .first()
    )

    if not appt:
        return render(request, "marketplace/qr_result.html", {
            "salon": salon,
            "success": False,
            "title": "Нет активных записей",
            "message": "У вас нет активных бронирований в этом заведении.",
        })

    # Mark as completed
    appt.status = "completed"
    appt.save(update_fields=["status"])

    # Optional: notify salon owner via Telegram
    try:
        owner_profile = getattr(salon.owner, "profile", None)
        if owner_profile and owner_profile.telegram_id:
            send_telegram_message(
                owner_profile.telegram_id,
                (
                    "<b>✅ Визит завершён</b>\n\n"
                    f"Клиент: {request.user.get_full_name() or request.user.username}\n"
                    f"Заведение: {salon.name}\n"
                    f"Бронь #{appt.id}\n"
                    "Статус изменён на «Выполнено» через QR-код."
                ),
            )
    except Exception as e:
        print(f"QR telegram notify error: {e}")

    return render(request, "marketplace/qr_result.html", {
        "salon": salon,
        "appointment": appt,
        "success": True,
        "title": "Спасибо за визит!",
        "message": f"Ваше бронирование в «{salon.name}» отмечено как завершённое.",
    })


@login_required
def qr_code_image(request, salon_id):
    """
    Returns PNG of the salon's QR code.
    Only salon owner can access.
    """
    import qrcode
    salon = get_object_or_404(Salon, pk=salon_id)

    if salon.owner != request.user and not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    # Build the full URL the QR points to
    qr_url = request.build_absolute_uri(
        f"/qr/{salon.id}/{salon.qr_token}/"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#101928", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="qr_{salon.id}.png"'
    return response


@login_required
def qr_print_page(request, salon_id):
    """
    Printable page with the QR code, salon name, instructions.
    Owner downloads/prints this and sticks it on the wall.
    """
    salon = get_object_or_404(Salon, pk=salon_id)

    if salon.owner != request.user and not request.user.is_staff:
        return HttpResponse("Forbidden", status=403)

    qr_url = request.build_absolute_uri(
        f"/qr/{salon.id}/{salon.qr_token}/"
    )

    return render(request, "marketplace/qr_print.html", {
        "salon": salon,
        "qr_url": qr_url,
    })

@login_required
@require_POST
def qr_complete_booking(request, appointment_id):
    """
    AJAX endpoint called from the 'My Bookings' page after the user scans a QR.
    Expects POST body: {salon_id, token}
    Verifies that the scanned salon matches the booking's salon, then marks completed.
    """
    appt = get_object_or_404(
        Appointment.objects.select_related("salon"),
        pk=appointment_id,
        client=request.user,
    )

    salon_id = request.POST.get("salon_id")
    token = request.POST.get("token", "").strip()

    if not salon_id or not token:
        return JsonResponse({"ok": False, "error": "Missing salon_id or token"}, status=400)

    # Verify scanned QR matches the booking's salon
    try:
        salon_id_int = int(salon_id)
    except ValueError:
        return JsonResponse({"ok": False, "error": "Invalid salon_id"}, status=400)

    if appt.salon_id != salon_id_int:
        return JsonResponse({
            "ok": False,
            "error": "QR-код не совпадает с этим бронированием. Сканируйте код в правильном заведении."
        }, status=400)

    if appt.salon.qr_token != token:
        return JsonResponse({
            "ok": False,
            "error": "Неверный QR-код."
        }, status=400)

    if appt.status not in ("pending", "confirmed"):
        return JsonResponse({
            "ok": False,
            "error": f"Бронирование уже имеет статус «{appt.get_status_display()}»."
        }, status=400)

    # Complete it
    appt.status = "completed"
    appt.save(update_fields=["status"])

    # Optional: telegram notify owner
    try:
        owner_profile = getattr(appt.salon.owner, "profile", None)
        if owner_profile and owner_profile.telegram_id:
            send_telegram_message(
                owner_profile.telegram_id,
                (
                    "<b>✅ Визит завершён (QR)</b>\n\n"
                    f"Клиент: {request.user.get_full_name() or request.user.username}\n"
                    f"Заведение: {appt.salon.name}\n"
                    f"Бронь #{appt.id}"
                ),
            )
    except Exception as e:
        print(f"QR telegram notify error: {e}")

    return JsonResponse({
        "ok": True,
        "message": "Визит подтверждён! Статус: Выполнено.",
        "appointment_id": appt.id,
    })