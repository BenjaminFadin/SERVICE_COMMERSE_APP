from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import BookingForm
from .models import Appointment, Category, Master, Salon, Service
from .utils import get_available_slots


def home(request):
    categories = Category.objects.all()
    return render(request, "marketplace/category_list.html", {"categories": categories})


def salon_list(request, category_slug=None):
    salons = Salon.objects.select_related("category", "owner").prefetch_related("services").all()
    category = None
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        salons = salons.filter(category=category)

    return render(
        request,
        "marketplace/salon_list.html",
        {"salons": salons, "category": category},
    )


def salon_detail(request, salon_id):
    salon = get_object_or_404(Salon.objects.select_related("category"), pk=salon_id)
    services = salon.services.all()
    masters = salon.masters.filter(is_active=True)
    return render(
        request,
        "marketplace/salon_detail.html",
        {"salon": salon, "services": services, "masters": masters},
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

            # server-side verify slot is still free
            slots = get_available_slots(
                salon=salon,
                master=master,
                service=service,
                date_obj=form.cleaned_data["date"],
            )
            if start_dt not in slots:
                form.add_error(None, "Selected time is no longer available. Please choose another slot.")
            else:
                Appointment.objects.create(
                    client=request.user,
                    salon=salon,
                    master=master,
                    service=service,
                    start_time=start_dt,
                    status="pending",
                    comment=form.cleaned_data.get("comment", ""),
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


@require_GET
def api_slots(request, salon_id, service_id):
    """
    GET params: master=<id>&date=YYYY-MM-DD
    returns: { slots: ["10:00", "10:15", ...] }
    """
    salon = get_object_or_404(Salon, pk=salon_id)
    service = get_object_or_404(Service, pk=service_id, salon=salon)

    master_id = request.GET.get("master")
    date_str = request.GET.get("date")
    if not master_id or not date_str:
        return JsonResponse({"slots": []})

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({"slots": []})

    master = salon.masters.filter(pk=master_id, is_active=True).first()
    if not master:
        return JsonResponse({"slots": []})

    slots = get_available_slots(salon=salon, master=master, service=service, date_obj=date_obj)
    return JsonResponse({"slots": [timezone.localtime(s).strftime("%H:%M") for s in slots]})


@login_required
def owner_dashboard(request):
    salons = request.user.salons.all()
    salon = salons.first()
    if not salon:
        return render(request, "business/dashboard.html", {"salon": None, "bookings": []})

    today = timezone.localdate()
    bookings = (
        Appointment.objects.filter(salon=salon, start_time__date=today)
        .select_related("client", "service", "master")
    )
    return render(request, "business/dashboard.html", {"salon": salon, "bookings": bookings})


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
