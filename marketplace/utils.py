from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

import requests
from django.conf import settings

from .models import Appointment, SalonWorkingHours


def get_available_slots(*, salon, master, service, date_obj, interval_minutes=15):
    """
    Returns list[datetime] (timezone-aware) for available start times.

    Rules:
    - uses SalonWorkingHours for weekday schedule
    - excludes closed days / missing working hours
    - excludes overlaps with existing appointments (pending/confirmed/completed)
    - excludes past times if date_obj is today
    """

    # 1) Working hours for this weekday
    wh = (
        SalonWorkingHours.objects
        .filter(salon=salon, weekday=date_obj.weekday())
        .first()
    )

    if not wh or wh.is_closed or not wh.open_time or not wh.close_time:
        return []

    # 2) Build aware start/end window for that date
    tz = timezone.get_current_timezone()

    start_naive = datetime.combine(date_obj, wh.open_time)
    end_naive = datetime.combine(date_obj, wh.close_time)

    start_dt = timezone.make_aware(start_naive, tz)
    end_dt = timezone.make_aware(end_naive, tz)

    # If close_time is past midnight (rare) you can handle it like this:
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    duration = timedelta(minutes=int(service.duration_minutes))
    step = timedelta(minutes=int(interval_minutes))

    # Latest start time so that service fits before closing
    latest_start = end_dt - duration
    if latest_start < start_dt:
        return []

    # 3) Pull existing appointments to exclude overlaps
    # NOTE: you must have end_time saved (your Appointment.save() sets it)
    busy = (
        Appointment.objects
        .filter(master=master, salon=salon)
        .filter(status__in=["pending", "confirmed", "completed"])
        .filter(start_time__lt=end_dt, end_time__gt=start_dt)  # overlaps window
        .values_list("start_time", "end_time")
    )

    busy_ranges = []
    for a_start, a_end in busy:
        if timezone.is_naive(a_start):
            a_start = timezone.make_aware(a_start, tz)
        if timezone.is_naive(a_end):
            a_end = timezone.make_aware(a_end, tz)
        busy_ranges.append((a_start, a_end))

    # 4) Generate candidates
    now = timezone.localtime(timezone.now(), tz)
    candidates = []
    t = start_dt
    while t <= latest_start:
        # exclude past times if today
        if date_obj == now.date() and t <= now:
            t += step
            continue

        # overlap check
        cand_end = t + duration
        overlapped = False
        for b_start, b_end in busy_ranges:
            if t < b_end and cand_end > b_start:
                overlapped = True
                break

        if not overlapped:
            candidates.append(t)

        t += step

    return candidates


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_telegram_message(chat_id: str, text: str):
    if not chat_id:
        return False

    url = TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        print("Telegram:", response.status_code, response.text)
        return True
    except Exception as e:
        print("Telegram error:", e)
        return False
