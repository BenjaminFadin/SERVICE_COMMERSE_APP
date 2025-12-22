from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.home, name="home"),
    path("category/<slug:category_slug>/", views.salon_list, name="salon_list_by_category"),
    path("salons/", views.salon_list, name="salon_list"),
    path("salon/<int:salon_id>/", views.salon_detail, name="salon_detail"),

    path("salon/<int:salon_id>/service/<int:service_id>/book/", views.booking_start, name="booking_start"),
    path("salon/<int:salon_id>/booking/success/", views.booking_success, name="booking_success"),

    path("api/salon/<int:salon_id>/service/<int:service_id>/slots/", views.api_slots, name="api_slots"),

    path("business/dashboard/", views.owner_dashboard, name="owner_dashboard"),
    path('ajax/booking-form/<int:salon_id>/<int:service_id>/', views.ajax_booking_form, name='ajax_booking_form'),
]

