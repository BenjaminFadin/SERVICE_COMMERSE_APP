from datetime import datetime

from django.db.models import Q, Exists, OuterRef, Prefetch
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .forms import BookingForm
from .models import Appointment, Category, Master, Salon, Service
from .utils import get_available_slots, send_telegram_message


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

    if request.method == "POST":
        form = BookingForm(request.POST, salon=salon)
        if form.is_valid():
            master = form.cleaned_data["master"]
            start_dt = form.build_start_datetime()

            slots = get_available_slots(
                salon=salon,
                master=master,
                service=service,
                date_obj=form.cleaned_data["date"],
            )

            if start_dt not in slots:
                form.add_error(None, "Selected time is no longer available.")
            else:
                appointment = Appointment.objects.create(
                    client=request.user,
                    salon=salon,
                    master=master,
                    service=service,
                    start_time=start_dt,
                    status="pending",
                    comment=form.cleaned_data.get("comment", ""),
                )

                # -----------------------------
                # TELEGRAM NOTIFICATIONS
                # -----------------------------
                customer_profile = getattr(request.user, "profile", None)
                provider_profile = getattr(salon.owner, "profile", None)
                
                print(customer_profile.telegram_id)
                print(provider_profile.telegram_id)
                
                # import time
                # time.sleep(200)
                
                start_time = timezone.localtime(start_dt).strftime("%d.%m.%Y %H:%M")

                # Customer
                if customer_profile and customer_profile.telegram_id:
                    print(customer_profile)
                    
                    send_telegram_message(
                        customer_profile.telegram_id,
                        (
                            "<b>Booking Confirmed</b>\n\n"
                            f"Salon: {salon.name}\n"
                            f"Service: {service.name}\n"
                            f"Time: {start_time}"
                        ),
                    )

                # Provider
                if provider_profile and provider_profile.telegram_id:
                    print(provider_profile)
                    
                    send_telegram_message(
                        provider_profile.telegram_id,
                        (
                            "<b>New Booking</b>\n\n"
                            f"Client: {request.user.get_full_name() or request.user.username}\n"
                            f"Service: {service.name}\n"
                            f"Time: {start_time}"
                        ),
                    )

                return redirect("marketplace:booking_success", salon_id=salon.id)

    else:
        form = BookingForm(salon=salon, initial={"date": timezone.localdate()})

    return render(
        request,
        "marketplace/booking_start.html",
        {"salon": salon, "service": service, "form": form},
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

    # Fetching split datasets for the UI
    bookings_today = base_query.filter(start_time__date=today).select_related("client", "service", "master").order_by('start_time')
    
    bookings_upcoming = base_query.filter(start_time__date__gt=today).select_related("client", "service", "master").order_by('start_time')
    
    bookings_past = base_query.filter(start_time__date__lt=today).select_related("client", "service", "master").order_by('-start_time')

    return render(request, "business/dashboard.html", {
        "salon": target_salon,
        "bookings_today": bookings_today,
        "bookings_upcoming": bookings_upcoming,
        "bookings_past": bookings_past,
        "today": today
    })

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
    
    # Get appointments where the current user is the client
    bookings = Appointment.objects.filter(client=request.user).select_related('salon', 'service', 'master')
    
    upcoming_bookings = bookings.filter(start_time__gte=now).order_by('start_time')
    past_bookings = bookings.filter(start_time__lt=now).order_by('-start_time')

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