import uuid
import secrets
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator


def pc_logo_upload_to(instance, filename):  # noqa: ARG001
    now = timezone.localtime()
    return f"pc_club_logos/{now:%Y/%m/%d}/{uuid.uuid4().hex[:8]}.webp"


def pc_cover_upload_to(instance, filename):  # noqa: ARG001
    now = timezone.localtime()
    return f"pc_club_covers/{now:%Y/%m/%d}/{uuid.uuid4().hex[:8]}.webp"


def pc_photo_upload_to(instance, filename):  # noqa: ARG001
    now = timezone.localtime()
    return f"pc_club_photos/{now:%Y/%m/%d}/{uuid.uuid4().hex[:8]}.webp"


def _process_image_to_webp(image_field, max_size=400):
    """Resize uploaded image and convert to WebP."""
    import os as _os
    from io import BytesIO
    from django.core.files.base import ContentFile
    from PIL import Image

    img = Image.open(image_field)
    img = img.convert("RGB")
    img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=85, method=6)
    buf.seek(0)
    base = _os.path.splitext(_os.path.basename(getattr(image_field, "name", "logo") or "logo"))[0]
    return ContentFile(buf.read(), name=f"{base}.webp")


def _is_new_upload(field):
    try:
        from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
        return isinstance(field.file, (InMemoryUploadedFile, TemporaryUploadedFile))
    except Exception:
        return False


class PCClub(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pc_clubs', verbose_name="Владелец"
    )
    category = models.ForeignKey(
        'marketplace.Category', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='pc_clubs', verbose_name="Категория"
    )
    description_ru = models.TextField(blank=True, verbose_name="Описание (RU)")
    description_en = models.TextField(blank=True, verbose_name="Описание (EN)")
    description_uz = models.TextField(blank=True, verbose_name="Описание (UZ)")
    address = models.TextField(verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    logo = models.ImageField(upload_to=pc_logo_upload_to, blank=True, null=True, verbose_name="Логотип")
    logo_url = models.URLField(max_length=500, blank=True, verbose_name="URL логотипа (демо/внешний)")
    cover = models.ImageField(upload_to=pc_cover_upload_to, blank=True, null=True, verbose_name="Обложка")
    cover_url = models.URLField(max_length=500, blank=True, verbose_name="URL обложки (демо/внешний)")
    total_pcs = models.PositiveIntegerField(default=20, verbose_name="Всего ПК")
    qr_token = models.CharField(max_length=32, unique=True, blank=True, verbose_name="QR-токен")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PC Club"
        verbose_name_plural = "PC Clubs"

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = secrets.token_urlsafe(16).replace("-", "").replace("_", "")[:24]
        if self.logo and _is_new_upload(self.logo):
            try:
                self.logo = _process_image_to_webp(self.logo, max_size=400)
            except Exception:
                pass
        if self.cover and _is_new_upload(self.cover):
            try:
                self.cover = _process_image_to_webp(self.cover, max_size=1200)
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def pcs_booked_at(self, start_dt, end_dt, exclude_booking_id=None):
        qs = self.bookings.filter(
            status__in=['pending', 'confirmed'],
            start_time__lt=end_dt,
            end_time__gt=start_dt,
        )
        if exclude_booking_id:
            qs = qs.exclude(pk=exclude_booking_id)
        return qs.aggregate(total=models.Sum('quantity'))['total'] or 0

    def available_pcs(self, start_dt, end_dt):
        return self.total_pcs - self.pcs_booked_at(start_dt, end_dt)


class PCPlan(models.Model):
    pc_club = models.ForeignKey(PCClub, on_delete=models.CASCADE, related_name='plans', verbose_name="PC Club")
    name = models.CharField(max_length=100, verbose_name="Название тарифа")
    name_en = models.CharField(max_length=100, blank=True, verbose_name="Название (EN)")
    name_uz = models.CharField(max_length=100, blank=True, verbose_name="Название (UZ)")
    description_ru = models.TextField(blank=True, verbose_name="Описание")
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена за час (сум)")
    color = models.CharField(max_length=20, default="#00A3AD", verbose_name="Цвет карточки")
    icon_class = models.CharField(max_length=80, default="bi bi-pc-display", verbose_name="Bootstrap иконка")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок сортировки")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "PC Plan"
        verbose_name_plural = "PC Plans"
        ordering = ['sort_order', 'price_per_hour']

    def __str__(self):
        return f"{self.pc_club.name} – {self.name} ({self.price_per_hour}/ч)"


class PCAddress(models.Model):
    pc_club = models.OneToOneField(PCClub, on_delete=models.CASCADE, related_name='location')
    full_address = models.TextField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    map_link = models.URLField(max_length=500, blank=True)

    class Meta:
        verbose_name = "PC Club Address"

    def __str__(self):
        return f"Location for {self.pc_club.name}"


WEEKDAYS = [
    (0, _("Понедельник")),
    (1, _("Вторник")),
    (2, _("Среда")),
    (3, _("Четверг")),
    (4, _("Пятница")),
    (5, _("Суббота")),
    (6, _("Воскресенье")),
]


class PCWorkingHours(models.Model):
    pc_club = models.ForeignKey(PCClub, on_delete=models.CASCADE, related_name='working_hours')
    weekday = models.IntegerField(choices=WEEKDAYS)
    is_closed = models.BooleanField(default=False)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('pc_club', 'weekday')
        ordering = ['weekday']
        verbose_name = "PC Club Working Hours"

    def __str__(self):
        return f"{self.pc_club.name} – {self.get_weekday_display()}"


class PCBooking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    ]

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pc_bookings', verbose_name="Клиент"
    )
    pc_club = models.ForeignKey(PCClub, on_delete=models.CASCADE, related_name='bookings', verbose_name="PC Club")
    plan = models.ForeignKey(PCPlan, on_delete=models.SET_NULL, null=True, verbose_name="Тариф")
    quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)], verbose_name="Кол-во ПК"
    )
    hours = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1)], verbose_name="Часов"
    )
    start_time = models.DateTimeField(verbose_name="Начало")
    end_time = models.DateTimeField(verbose_name="Конец")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PC Booking"
        verbose_name_plural = "PC Bookings"
        ordering = ['-start_time']

    def __str__(self):
        plan_name = self.plan.name if self.plan else "?"
        return f"{self.client} → {self.pc_club.name} [{plan_name}] {timezone.localtime(self.start_time):%d.%m %H:%M}"


class PCPhoto(models.Model):
    pc_club = models.ForeignKey(PCClub, on_delete=models.CASCADE, related_name='photos', verbose_name="PC Club")
    image = models.ImageField(upload_to=pc_photo_upload_to, blank=True, null=True, verbose_name="Фото")
    photo_url = models.URLField(max_length=500, blank=True, verbose_name="URL фото (демо/внешний)")
    caption = models.CharField(max_length=100, blank=True, verbose_name="Описание")
    is_main = models.BooleanField(default=False, verbose_name="Главное фото?")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "PC Club Photo"
        verbose_name_plural = "PC Club Photos"
        ordering = ['-is_main', '-created_at']

    @property
    def src(self):
        if self.image:
            return self.image.url
        return self.photo_url

    def save(self, *args, **kwargs):
        if self.image and _is_new_upload(self.image):
            try:
                self.image = _process_image_to_webp(self.image, max_size=1200)
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Photo for {self.pc_club.name}"

