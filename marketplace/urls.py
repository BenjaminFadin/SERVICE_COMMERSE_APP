from django.urls import path
from . import views

app_name = "marketplace"

urlpatterns = [
    path("", views.home, name="home"),
    path("category/<slug:category_slug>/", views.salon_list, name="salon_list_by_category"),
    path("salons/", views.salon_list, name="salon_list"),
    path("salon/<int:salon_id>/", views.salon_detail, name="salon_detail"),
    path("my-bookings/", views.my_bookings, name="my_bookings"),
    path("booking/<int:appointment_id>/cancel/", views.cancel_booking, name="cancel_booking"),

    path("salon/<int:salon_id>/service/<int:service_id>/book/", views.booking_start, name="booking_start"),
    path("salon/<int:salon_id>/booking/success/", views.booking_success, name="booking_success"),

    path("api/salon/<int:salon_id>/service/<int:service_id>/slots/", views.api_slots, name="api_slots"),

    path("business/dashboard/", views.owner_dashboard, name="owner_dashboard"),

    # NEW: provider actions on pending bookings
    path("business/booking/<int:appointment_id>/accept/", views.accept_booking, name="accept_booking"),
    path("business/booking/<int:appointment_id>/decline/", views.decline_booking, name="decline_booking"),

    # QR Scan side
    # Customer scan endpoint — short URL because it's embedded in the QR
    path("qr/<int:salon_id>/<str:token>/", views.qr_checkout, name="qr_checkout"),
    path("appointment/<int:appointment_id>/qr-complete/", views.qr_complete_booking, name="qr_complete_booking"),
    # Owner-only — view the QR image directly (for embedding)
    path("salon/<int:salon_id>/qr.png", views.qr_code_image, name="qr_code_image"),

    # Owner-only — printable QR page
    path("salon/<int:salon_id>/qr/print/", views.qr_print_page, name="qr_print_page"),


    path('ajax/booking-form/<int:salon_id>/<int:service_id>/', views.ajax_booking_form, name='ajax_booking_form'),
    path('search/', views.search_view, name='salon_search'),
    path("business-lead/", views.submit_business_lead, name="submit_business_lead"),
]