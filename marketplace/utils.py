import os
import uuid
from datetime import datetime, timedelta
from django.utils import timezone
from marketplace.models import Appointment, SalonWorkingHours



def get_available_slots(*, salon, master, service, date_obj, step_minutes=15):
    """
    Returns list of aware datetimes (start slots) available for booking.
    date_obj: python date (not datetime).
    """
    weekday = date_obj.weekday()
    wh = SalonWorkingHours.objects.filter(salon=salon, weekday=weekday).first()
    if not wh or wh.is_closed:
        return []

    tz = timezone.get_current_timezone()

    start_dt = timezone.make_aware(datetime.combine(date_obj, wh.open_time), tz)
    end_dt = timezone.make_aware(datetime.combine(date_obj, wh.close_time), tz)

    duration = timedelta(minutes=service.duration_minutes)
    step = timedelta(minutes=step_minutes)

    # existing appointments (ignore cancelled)
    existing = Appointment.objects.filter(
        salon=salon,
        master=master,
        status__in=["pending", "confirmed", "completed"],
        start_time__date=date_obj,
    ).values("start_time", "end_time")

    busy = [(e["start_time"], e["end_time"]) for e in existing]

    slots = []
    cur = start_dt
    while cur + duration <= end_dt:
        candidate_end = cur + duration
        overlaps = any(cur < b_end and candidate_end > b_start for (b_start, b_end) in busy)
        if not overlaps:
            slots.append(cur)
        cur += step

    return slots
