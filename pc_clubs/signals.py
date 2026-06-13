from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import PCBooking
from marketplace.utils import send_telegram_message, send_sms


@receiver(post_save, sender=PCBooking)
def notify_pc_booking_created(sender, instance, created, **kwargs):
    if not created:
        return

    client = instance.client
    client_profile = getattr(client, "profile", None)
    provider_user = instance.pc_club.owner
    provider_profile = getattr(provider_user, "profile", None)

    start_dt = timezone.localtime(instance.start_time).strftime("%d.%m.%Y %H:%M")
    plan_name = instance.plan.name if instance.plan else "—"
    club_name = instance.pc_club.name

    client_tg = (
        "<b>⏳ Заявка отправлена</b>\n\n"
        f"Клуб: {club_name}\n"
        f"Тариф: {plan_name}\n"
        f"Мест: {instance.quantity} ПК\n"
        f"Часов: {instance.hours}\n"
        f"Время: {start_dt}\n\n"
        "Ожидайте подтверждения от клуба."
    )
    owner_tg = (
        "<b>🔔 Новая заявка на ПК</b>\n\n"
        f"Клуб: {club_name}\n"
        f"Клиент: {client.get_full_name() or client.username}\n"
        f"Тариф: {plan_name}\n"
        f"Мест: {instance.quantity} ПК\n"
        f"Часов: {instance.hours}\n"
        f"Время: {start_dt}\n\n"
        "Откройте дашборд, чтобы принять или отклонить."
    )

    # Telegram
    if client_profile and client_profile.telegram_id:
        send_telegram_message(client_profile.telegram_id, client_tg)
    if provider_profile and provider_profile.telegram_id:
        send_telegram_message(provider_profile.telegram_id, owner_tg)

    # SMS
    client_phone = getattr(client_profile, "phone", "") if client_profile else ""
    owner_phone = getattr(provider_profile, "phone", "") if provider_profile else ""
    sms_client = f"Zayavka otpravlena! Klub: {club_name}, {plan_name}, {start_dt}. Ozhidayte podtverzhdeniya."
    sms_owner = f"Novaya zayavka na PK! Klient: {client.get_full_name() or client.username}, {plan_name}, {start_dt}."
    send_sms(client_phone, sms_client)
    send_sms(owner_phone, sms_owner)
