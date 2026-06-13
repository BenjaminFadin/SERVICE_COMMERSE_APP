from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from marketplace.models import Category

from .models import PCBooking, PCClub, PCPlan


def pc_club_list(request, category_slug=None):
    category = None
    clubs_qs = PCClub.objects.select_related('category').prefetch_related('plans')

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        descendants = category.get_descendants(include_self=True)
        clubs_qs = clubs_qs.filter(category__in=descendants)
    else:
        pc_cats = Category.objects.filter(is_pc_club=True)
        if pc_cats.exists():
            all_desc = Category.objects.none()
            for pc_cat in pc_cats:
                all_desc = all_desc | pc_cat.get_descendants(include_self=True)
            clubs_qs = clubs_qs.filter(category__in=all_desc)

    return render(request, 'pc_clubs/list.html', {
        'clubs': clubs_qs,
        'category': category,
    })


def pc_club_detail(request, pk):
    club = get_object_or_404(
        PCClub.objects
            .prefetch_related('plans', 'working_hours')
            .select_related('category', 'location'),
        pk=pk,
    )
    plans = club.plans.filter(is_active=True)
    working_hours = club.working_hours.all()

    booked_success = request.GET.get('booked') == '1'

    return render(request, 'pc_clubs/detail.html', {
        'club': club,
        'plans': plans,
        'working_hours': working_hours,
        'today_weekday': timezone.localtime().weekday(),
        'booked_success': booked_success,
    })


@login_required
@require_POST
def pc_club_book(request, pk):
    club = get_object_or_404(PCClub, pk=pk)

    plan_id  = request.POST.get('plan_id')
    quantity = request.POST.get('quantity', '1')
    hours    = request.POST.get('hours', '1')
    date_str = request.POST.get('date', '')
    time_str = request.POST.get('time', '')
    comment  = request.POST.get('comment', '')

    if not all([plan_id, date_str, time_str]):
        return JsonResponse({'ok': False, 'error': 'Заполните все обязательные поля.'}, status=400)

    try:
        quantity = max(1, int(quantity))
        hours    = max(1, int(hours))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Неверное значение количества или часов.'}, status=400)

    plan = get_object_or_404(PCPlan, pk=plan_id, pc_club=club, is_active=True)

    tz = timezone.get_current_timezone()
    try:
        start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        start_time = timezone.make_aware(start_time, tz)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Неверный формат даты или времени.'}, status=400)

    if start_time < timezone.now():
        return JsonResponse({'ok': False, 'error': 'Нельзя бронировать прошедшее время.'}, status=400)

    end_time = start_time + timedelta(hours=hours)

    available = club.available_pcs(start_time, end_time)
    if quantity > available:
        return JsonResponse({
            'ok': False,
            'error': f'Доступно только {available} ПК на это время.',
        }, status=400)

    PCBooking.objects.create(
        client=request.user,
        pc_club=club,
        plan=plan,
        quantity=quantity,
        hours=hours,
        start_time=start_time,
        end_time=end_time,
        comment=comment,
        status='pending',
    )

    return JsonResponse({'ok': True, 'redirect': f'/pc-clubs/{club.pk}/?booked=1'})


@login_required
@require_POST
def pc_booking_change_status(request, booking_id):
    from marketplace.utils import send_telegram_message, send_sms

    booking = get_object_or_404(
        PCBooking.objects.select_related("pc_club", "client", "client__profile", "plan"),
        pk=booking_id,
    )

    if booking.pc_club.owner != request.user and not request.user.is_staff:
        return JsonResponse({"ok": False, "error": "Доступ запрещён."}, status=403)

    if booking.status != "pending":
        return JsonResponse({
            "ok": False,
            "error": f"Нельзя изменить статус с «{booking.get_status_display()}».",
        }, status=400)

    new_status = request.POST.get("status", "").strip()
    if new_status not in ("confirmed", "cancelled"):
        return JsonResponse({"ok": False, "error": "Недопустимое действие."}, status=400)

    booking.status = new_status
    booking.save(update_fields=["status"])

    # Notify client
    try:
        client = booking.client
        client_profile = getattr(client, "profile", None)
        plan_name = booking.plan.name if booking.plan else "—"
        start_dt = timezone.localtime(booking.start_time).strftime("%d.%m.%Y %H:%M")

        labels = {
            "confirmed": "✅ Бронирование подтверждено",
            "cancelled": "❌ Бронирование отклонено",
        }
        tg_text = (
            f"<b>{labels[new_status]}</b>\n\n"
            f"Клуб: {booking.pc_club.name}\n"
            f"Тариф: {plan_name}\n"
            f"Время: {start_dt}\n"
            f"Бронь #{booking.id}"
        )
        label_sms = "podtverzhdeno" if new_status == "confirmed" else "otkloneno"
        sms_text = (
            f"Bronirovanie #{booking.id} {label_sms}! "
            f"Klub: {booking.pc_club.name}, {plan_name}, {start_dt}."
        )

        if client_profile and client_profile.telegram_id:
            send_telegram_message(client_profile.telegram_id, tg_text)
        phone = getattr(client_profile, "phone", "") if client_profile else ""
        send_sms(phone, sms_text)

    except Exception as e:
        print(f"PC booking notify error: {e}")

    return JsonResponse({
        "ok": True,
        "status": new_status,
        "status_display": booking.get_status_display(),
        "booking_id": booking.id,
    })
