import math
from datetime import datetime
from django.http import HttpResponse
from django.db.models import Q, Exists, OuterRef, Prefetch, Min
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


def _haversine_km(lat1, lng1, lat2, lng2):
    """Distance between two coordinates in kilometers."""
    R = 6371  # Earth radius in km
    rlat1 = math.radians(float(lat1))
    rlat2 = math.radians(float(lat2))
    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def nearby_salons(request):
    """Show salons sorted by distance from the user's coordinates."""
    try:
        user_lat = float(request.GET.get("lat", ""))
        user_lng = float(request.GET.get("lng", ""))
    except (ValueError, TypeError):
        return render(request, "marketplace/nearby_salons.html", {
            "error": "Не удалось определить ваше местоположение. Разрешите доступ к геолокации и попробуйте ещё раз.",
            "salons_with_distance": [],
        })

    # Optional radius filter (default 20 km)
    try:
        radius_km = float(request.GET.get("radius", 20))
    except (ValueError, TypeError):
        radius_km = 20

    # Get all salons that have coordinates
    salons = Salon.objects.select_related("location", "category").filter(
        location__latitude__isnull=False,
        location__longitude__isnull=False,
    )

    results = []
    for s in salons:
        dist = _haversine_km(user_lat, user_lng, s.location.latitude, s.location.longitude)
        if dist <= radius_km:
            results.append({"salon": s, "distance_km": round(dist, 1)})

    # Sort nearest first
    results.sort(key=lambda x: x["distance_km"])

    return render(request, "marketplace/nearby_salons.html", {
        "salons_with_distance": results,
        "user_lat": user_lat,
        "user_lng": user_lng,
        "radius_km": radius_km,
        "total_found": len(results),
    })

def auto_complete_overdue_appointments(salon=None, user=None):
    """
    Lazy auto-complete:
    Find confirmed appointments whose end time has passed and mark them completed.
    Optionally scope to a single salon (for owner dashboard) or a single user (for my_bookings).
    """
    from datetime import timedelta
    now = timezone.now()

    qs = Appointment.objects.filter(status="confirmed")
    if salon:
        qs = qs.filter(salon=salon)
    if user:
        qs = qs.filter(client=user)

    # Limit to recent ones (avoid scanning whole history)
    qs = qs.filter(start_time__gte=now - timedelta(days=7))

    updated_count = 0
    for appt in qs:
        # Compute end time priority: end_time > hours > service.duration > 1h default
        end_dt = appt.end_time
        if not end_dt:
            if appt.service:
                end_dt = appt.start_time + timedelta(minutes=appt.service.duration_minutes)
            elif appt.hours:
                end_dt = appt.start_time + timedelta(hours=appt.hours)
            else:
                end_dt = appt.start_time + timedelta(hours=1)

        if end_dt < now:
            appt.status = "completed"
            appt.save(update_fields=["status"])
            updated_count += 1
    return updated_count


@login_required
@require_POST
def appointment_change_status(request, appointment_id):
    """
    Owner-only: accept or cancel a pending booking.
    Allowed transitions:
      - pending -> confirmed (accept)
      - pending -> cancelled (cancel)
    """
    appt = get_object_or_404(
        Appointment.objects.select_related("salon", "client", "service"),
        pk=appointment_id,
    )

    # Permission: only the salon owner (or staff)
    if appt.salon.owner != request.user and not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "Доступ запрещён."}, status=403)

    new_status = request.POST.get("status", "").strip()
    if appt.status != "pending":
        return JsonResponse({
            "ok": False,
            "error": f"Нельзя изменить статус с «{appt.get_status_display()}». Действие доступно только для ожидающих бронирований."
        }, status=400)

    if new_status not in ("confirmed", "cancelled"):
        return JsonResponse({
            "ok": False,
            "error": "Недопустимое действие."
        }, status=400)

    appt.status = new_status
    appt.save(update_fields=["status"])

    # Notify client via Telegram
    try:
        client_profile = getattr(appt.client, "profile", None)
        if client_profile and client_profile.telegram_id:
            labels = {
                "confirmed": "✅ Ваше бронирование подтверждено",
                "cancelled": "❌ Ваше бронирование отменено заведением",
            }
            send_telegram_message(
                client_profile.telegram_id,
                (
                    f"<b>{labels.get(new_status, new_status)}</b>\n\n"
                    f"Заведение: {appt.salon.name}\n"
                    f"Время: {timezone.localtime(appt.start_time).strftime('%Y-%m-%d %H:%M')}\n"
                    f"Бронь #{appt.id}"
                ),
            )
    except Exception as e:
        print(f"Telegram notify error: {e}")

    return JsonResponse({
        "ok": True,
        "status": new_status,
        "status_display": appt.get_status_display(),
        "appointment_id": appt.id,
    })

def search_view(request):
    query = request.GET.get('q', '').strip()
    location = request.GET.get('location', '').strip()
    
    # Start with all active salons (or masters)
    results = Salon.objects.all()

    if query:
        # Creative part: Search across multiple related models
        results = results.filter(
            Q(name__icontains=query) | 
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
    query    = (request.GET.get("q") or "").strip()
    location = (request.GET.get("location") or "").strip()
    sort     = (request.GET.get("sort") or "").strip()
    user_lat = (request.GET.get("lat") or "").strip()
    user_lng = (request.GET.get("lng") or "").strip()

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

    # Search
    if query:
        service_match = Service.objects.filter(
            salon_id=OuterRef("pk"),
        ).filter(
            Q(name_ru__icontains=query) |
            Q(name_en__icontains=query) |
            Q(name_uz__icontains=query)
        )
        salons_qs = salons_qs.filter(
            Q(name__icontains=query) |
            Q(category__name_ru__icontains=query) |
            Q(category__name_en__icontains=query) |
            Q(category__name_uz__icontains=query) |
            Exists(service_match)
        )

    if location:
        salons_qs = salons_qs.filter(address__icontains=location)

    # Sorting / filtering
    if sort == "price_asc":
        salons_qs = salons_qs.annotate(min_price=Min("services__price")).order_by("min_price")
    elif sort == "price_desc":
        salons_qs = salons_qs.annotate(min_price=Min("services__price")).order_by("-min_price")
    elif sort == "open_now":
        now_local = timezone.localtime()
        salons_qs = salons_qs.filter(
            working_hours__weekday=now_local.weekday(),
            working_hours__is_closed=False,
            working_hours__open_time__lte=now_local.time(),
            working_hours__close_time__gte=now_local.time(),
        )

    # Prefetch services for card display
    salons_qs = salons_qs.prefetch_related(
        Prefetch(
            "services",
            queryset=Service.objects.only(
                "id", "salon_id", "name_ru", "name_en", "name_uz", "price", "duration_minutes", "img"
            ),
        )
    )

    # Nearest: Python-side haversine sort (Paginator handles lists too)
    if sort == "nearest" and user_lat and user_lng:
        try:
            lat = float(user_lat)
            lng = float(user_lng)
            salons_list = list(salons_qs.select_related("location"))

            def _dist(s):
                loc = getattr(s, "location", None)
                if loc and loc.latitude and loc.longitude:
                    return _haversine_km(lat, lng, float(loc.latitude), float(loc.longitude))
                return 99999

            salons_list.sort(key=_dist)
            paginator = Paginator(salons_list, 10)
        except (ValueError, TypeError):
            paginator = Paginator(salons_qs, 10)
    else:
        paginator = Paginator(salons_qs, 10)

    salons_page = paginator.get_page(request.GET.get("page"))

    # Build base URL for sort chips (keeps q/location/lat/lng, strips sort/page)
    from urllib.parse import urlencode
    base_params = {}
    if query:
        base_params["q"] = query
    if location:
        base_params["location"] = location
    if user_lat and user_lng:
        base_params["lat"] = user_lat
        base_params["lng"] = user_lng
    qs_prefix = ("?" + urlencode(base_params) + "&") if base_params else "?"
    sort_base = request.path + qs_prefix   # append "sort=xxx" directly

    return render(
        request,
        "marketplace/salon_list.html",
        {
            "salons": salons_page,
            "category": category,
            "subcategories": subcategories,
            "search_query": query,
            "search_location": location,
            "sort": sort,
            "user_lat": user_lat,
            "user_lng": user_lng,
            "sort_base": sort_base,
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
    from pc_clubs.models import PCClub, PCBooking

    salons = request.user.salons.all()
    master_profile = getattr(request.user, 'master_profile', None)
    user_pc_clubs = PCClub.objects.filter(owner=request.user)

    today = timezone.localdate()

    # ── Salon bookings ──────────────────────────────────────────────
    target_salon = None
    bookings_pending = Appointment.objects.none()
    bookings_today = Appointment.objects.none()
    bookings_upcoming = Appointment.objects.none()
    bookings_past = Appointment.objects.none()

    if salons.exists() or master_profile:
        if salons.exists():
            target_salon = salons.first()
            base_query = Appointment.objects.filter(salon=target_salon)
            auto_complete_overdue_appointments(salon=target_salon)
        else:
            target_salon = master_profile.salon
            base_query = Appointment.objects.filter(master=master_profile)
            auto_complete_overdue_appointments(salon=target_salon)

        bookings_pending = base_query.filter(status="pending").select_related(
            "client", "client__profile", "service", "master"
        ).order_by("start_time")
        bookings_today = (
            base_query.filter(start_time__date=today)
            .exclude(status="cancelled")
            .select_related("client", "service", "master")
            .order_by("start_time")
        )
        bookings_upcoming = (
            base_query.filter(start_time__date__gt=today)
            .exclude(status="cancelled")
            .select_related("client", "service", "master")
            .order_by("start_time")
        )
        bookings_past = (
            base_query.filter(start_time__date__lt=today)
            .select_related("client", "service", "master")
            .order_by("-start_time")
        )

    # ── PC club bookings ────────────────────────────────────────────
    pc_bookings_pending = PCBooking.objects.none()
    pc_bookings_today = PCBooking.objects.none()
    pc_bookings_upcoming = PCBooking.objects.none()
    pc_bookings_past = PCBooking.objects.none()

    if user_pc_clubs.exists():
        pc_base = (
            PCBooking.objects
            .filter(pc_club__in=user_pc_clubs)
            .select_related("client", "client__profile", "plan", "pc_club")
        )
        pc_bookings_pending = pc_base.filter(status="pending").order_by("start_time")
        pc_bookings_today = (
            pc_base.filter(start_time__date=today)
            .exclude(status="cancelled")
            .order_by("start_time")
        )
        pc_bookings_upcoming = (
            pc_base.filter(start_time__date__gt=today)
            .exclude(status="cancelled")
            .order_by("start_time")
        )
        pc_bookings_past = pc_base.filter(start_time__date__lt=today).order_by("-start_time")

    # Show "No Active Salon" page only if user has nothing at all
    has_anything = target_salon or user_pc_clubs.exists()

    return render(request, "business/dashboard.html", {
        "salon": target_salon,
        "bookings_pending": bookings_pending,
        "bookings_today": bookings_today,
        "bookings_upcoming": bookings_upcoming,
        "bookings_past": bookings_past,
        "today": today,
        "user_pc_clubs": user_pc_clubs,
        "pc_bookings_pending": pc_bookings_pending,
        "pc_bookings_today": pc_bookings_today,
        "pc_bookings_upcoming": pc_bookings_upcoming,
        "pc_bookings_past": pc_bookings_past,
        "has_anything": has_anything,
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

    # Lazy auto-complete: mark overdue confirmed bookings as completed
    auto_complete_overdue_appointments(user=request.user)

    bookings = Appointment.objects.filter(client=request.user).select_related(
        'salon', 'service', 'master'
    )

    # Upcoming = not past + not cancelled/completed
    upcoming_bookings = bookings.filter(
        start_time__gte=now,
    ).exclude(status__in=["cancelled", "completed"]).order_by('start_time')

    past_bookings = bookings.filter(
        start_time__lt=now,
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


@login_required
@require_POST
def appointment_change_status(request, appointment_id):
    """
    Owner-only: change appointment status.
    Allowed transitions:
      - pending   -> confirmed  (accept)
      - pending   -> cancelled  (decline)
      - confirmed -> completed  (mark done after visit)
      - confirmed -> cancelled  (cancel an accepted booking)
    """
    appt = get_object_or_404(
        Appointment.objects.select_related("salon", "client", "service"),
        pk=appointment_id,
    )

    if appt.salon.owner != request.user and not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "Доступ запрещён."}, status=403)

    new_status = request.POST.get("status", "").strip()
    valid_transitions = {
        "pending":   {"confirmed", "cancelled"},
        "confirmed": {"completed", "cancelled"},
    }
    allowed = valid_transitions.get(appt.status, set())
    if new_status not in allowed:
        return JsonResponse({
            "ok": False,
            "error": f"Нельзя изменить статус с «{appt.get_status_display()}» на «{new_status}»."
        }, status=400)

    appt.status = new_status
    appt.save(update_fields=["status"])

    # Notify client via Telegram
    try:
        client_profile = getattr(appt.client, "profile", None)
        if client_profile and client_profile.telegram_id:
            labels = {
                "confirmed": "✅ Ваше бронирование подтверждено",
                "cancelled": "❌ Ваше бронирование отменено заведением",
                "completed": "🎉 Ваш визит отмечен как выполненный",
            }
            send_telegram_message(
                client_profile.telegram_id,
                (
                    f"<b>{labels.get(new_status, new_status)}</b>\n\n"
                    f"Заведение: {appt.salon.name}\n"
                    f"Время: {timezone.localtime(appt.start_time).strftime('%Y-%m-%d %H:%M')}\n"
                    f"Бронь #{appt.id}"
                ),
            )
    except Exception as e:
        print(f"Telegram notify error: {e}")

    return JsonResponse({
        "ok": True,
        "status": new_status,
        "status_display": appt.get_status_display(),
        "appointment_id": appt.id,
    })