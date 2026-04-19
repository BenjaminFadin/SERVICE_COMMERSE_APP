from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Appointment
from .utils import send_telegram_message


@receiver(post_save, sender=Appointment)
def notify_booking_created(sender, instance, created, **kwargs):
    if not created:
        return

    # -------- CUSTOMER --------
    customer = instance.client
    customer_profile = getattr(customer, "profile", None)

    # -------- PROVIDER (Salon owner) --------
    provider_user = instance.salon.owner
    provider_profile = getattr(provider_user, "profile", None)

    start_time = timezone.localtime(instance.start_time).strftime("%Y-%m-%d %H:%M")

    # Message to CUSTOMER
    if customer_profile and customer_profile.telegram_id:
        send_telegram_message(
            customer_profile.telegram_id,
            (
                "<b>⏳ Booking Request Sent</b>\n\n"
                f"Salon: {instance.salon.name}\n"
                f"Service: {instance.service.name_ru}\n"
                f"Time: {start_time}\n\n"
                "Waiting for the provider to confirm your booking."
            ),
        )

    # Message to PROVIDER
    if provider_profile and provider_profile.telegram_id:
        send_telegram_message(
            provider_profile.telegram_id,
            (
                "<b>🔔 New Booking Request</b>\n\n"
                f"Client: {customer.get_full_name() or customer.username}\n"
                f"Service: {instance.service.name_ru}\n"
                f"Time: {start_time}\n\n"
                "Please open your dashboard to Accept or Decline."
            ),
        )

