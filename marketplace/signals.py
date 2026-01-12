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
                "<b>Booking Confirmed</b>\n\n"
                f"Salon: {instance.salon.name}\n"
                f"Service: {instance.service.name}\n"
                f"Time: {start_time}"
            ),
        )

    # Message to PROVIDER
    if provider_profile and provider_profile.telegram_id:
        send_telegram_message(
            provider_profile.telegram_id,
            (
                "<b>New Booking</b>\n\n"
                f"Client: {customer.get_full_name() or customer.username}\n"
                f"Service: {instance.service.name}\n"
                f"Time: {start_time}"
            ),
        )
