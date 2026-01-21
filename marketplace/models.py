import os
import uuid
from datetime import timedelta
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone



def salon_logo_upload_to(instance, filename):
    # 1. Split the name and extension
    name, ext = os.path.splitext(filename)
    
    # 2. Truncate the original name to the first 20 characters
    short_name = name[:20]
    
    # 3. Clean the extension (ensure lowercase)
    ext = ext.lower() or ".jpg"
    
    now = timezone.localtime()
    # 4. Return the path: folder/date/short_name + extension
    # We use uuid.uuid4().hex[:4] or similar if you want to ensure uniqueness 
    # even with truncated names, but here is the exact logic for 20 chars:
    return f"salon_logos/{now:%Y/%m/%d}/{short_name}{ext}"

def service_img_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = ".jpg"
    now = timezone.localtime()
    unique = uuid.uuid4().hex[:8]
    return f"services/{now:%Y/%m/%d}/{unique}{ext}"


def master_photo_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        ext = ".jpg"
    now = timezone.localtime()
    unique = uuid.uuid4().hex[:8]
    return f"masters/{now:%Y/%m/%d}/{unique}{ext}"


def salon_gallery_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    now = timezone.localtime()
    # Path: salon_photos/YYYY/MM/DD/salon_id_uuid.ext
    return f"salon_photos/{now:%Y/%m/%d}/{instance.salon.id}_{uuid.uuid4().hex[:6]}{ext}"


class MultilingualMixin(models.Model):
    class Meta:
        abstract = True

    def get_i18n(self, field_base: str, lang_code: str, default_lang: str = "ru"):
        """
        field_base example: "name" or "description"
        expects: field_base_ru, field_base_en, field_base_uz
        """
        lang_code = (lang_code or default_lang).lower()
        candidates = [
            f"{field_base}_{lang_code}",
            f"{field_base}_{default_lang}",
        ]
        for f in candidates:
            if hasattr(self, f):
                val = getattr(self, f)
                if val:
                    return val
        return ""


class Category(MultilingualMixin, models.Model):
    name_ru = models.CharField(max_length=100, verbose_name="Название (RU)")
    name_en = models.CharField(max_length=100, blank=True, verbose_name="Название (EN)")
    name_uz = models.CharField(max_length=100, blank=True, verbose_name="Название (UZ)")

    slug = models.SlugField(unique=True, verbose_name="URL метка")
    icon_class = models.CharField(
        max_length=80,
        blank=True,
        default="bi bi-grid",
        verbose_name="Bootstrap icon class"
    )
    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name_ru


class Salon(MultilingualMixin, models.Model):
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    name_uz = models.CharField(max_length=200, blank=True)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salons', verbose_name="Владелец")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='salons', verbose_name="Категория")
    description_ru = models.TextField(blank=True, verbose_name="Описание (RU)")
    description_en = models.TextField(blank=True, verbose_name="Описание (EN)")
    description_uz = models.TextField(blank=True, verbose_name="Описание (UZ)")

    address = models.TextField(verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон салона")
    logo = models.ImageField(upload_to=salon_logo_upload_to, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"

    def __str__(self):
        return self.name


class SalonPhoto(models.Model):
    salon = models.ForeignKey(
        Salon, 
        on_delete=models.CASCADE, 
        related_name='photos', 
        verbose_name="Салон"
    )
    image = models.ImageField(
        upload_to=salon_gallery_upload_to, 
        verbose_name="Фото"
    )
    caption = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Описание (необяз.)"
    )
    is_main = models.BooleanField(
        default=False, 
        verbose_name="Главное фото?"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Фото салона"
        verbose_name_plural = "Фотографии салона"
        ordering = ['-is_main', '-created_at']

    def __str__(self):
        return f"Photo for {self.salon.name_ru}"


class Service(MultilingualMixin, models.Model):
    name_ru = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    name_uz = models.CharField(max_length=200, blank=True)
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services', verbose_name="Салон")
    img = models.ImageField(
        upload_to=service_img_upload_to,
        blank=True,
        null=True,
        verbose_name="Изображение услуги"
    )

    description_ru = models.TextField(blank=True, verbose_name="Описание (RU)")
    description_en = models.TextField(blank=True, verbose_name="Описание (EN)")
    description_uz = models.TextField(blank=True, verbose_name="Описание (UZ)")

    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    duration_minutes = models.PositiveIntegerField(verbose_name="Длительность (мин)")

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return f"{self.name} - {self.price}"


class Master(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='masters', verbose_name="Салон")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='master_profile'
    )

    name = models.CharField(max_length=100, verbose_name="Имя мастера")

    specialization_ru = models.CharField(max_length=100, verbose_name="Специализация (RU)", blank=True)
    specialization_en = models.CharField(max_length=100, verbose_name="Специализация (EN)", blank=True)
    specialization_uz = models.CharField(max_length=100, verbose_name="Специализация (UZ)", blank=True)

    photo = models.ImageField(
        upload_to=master_photo_upload_to,
        blank=True,
        null=True,
        verbose_name="Фото"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"

    def __str__(self):
        return self.name


class SalonWorkingHours(models.Model):
    """
    Define salon opening hours per weekday (0=Mon .. 6=Sun).
    """
    WEEKDAYS = [
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
        (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")
    ]

    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.IntegerField(choices=WEEKDAYS)
    is_closed = models.BooleanField(default=False)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ("salon", "weekday")
        verbose_name = "График работы салона"
        verbose_name_plural = "Графики работы салонов"

    def clean(self):
        if not self.is_closed:
            if not self.open_time or not self.close_time:
                raise ValidationError("If not closed, open_time and close_time are required.")
            if self.open_time >= self.close_time:
                raise ValidationError("open_time must be earlier than close_time.")

    def __str__(self):
        return f"{self.salon} - {self.get_weekday_display()}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('confirmed', 'Подтверждено'),
        ('completed', 'Выполнено'),
        ('cancelled', 'Отменено'),
    ]

    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='appointments', verbose_name="Клиент")
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='appointments', verbose_name="Салон")
    master = models.ForeignKey(Master, on_delete=models.SET_NULL, null=True, related_name='appointments', verbose_name="Мастер")
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True, verbose_name="Услуга")

    start_time = models.DateTimeField(verbose_name="Время начала")
    end_time = models.DateTimeField(verbose_name="Время окончания", blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создано")

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ['-start_time']

    def clean(self):
        if not self.start_time or not self.service or not self.master:
            return

        # compute end time candidate
        end_candidate = self.start_time + timedelta(minutes=self.service.duration_minutes)

        # overlap check (ignore cancelled)
        qs = Appointment.objects.filter(
            master=self.master,
            status__in=["pending", "confirmed", "completed"]
        ).exclude(pk=self.pk)

        # Overlap condition: start < other_end AND end > other_start
        qs = qs.filter(start_time__lt=end_candidate, end_time__gt=self.start_time)
        if qs.exists():
            raise ValidationError("This time is already booked for the selected master.")

    def save(self, *args, **kwargs):
        if self.start_time and self.service and not self.end_time:
            self.end_time = self.start_time + timedelta(minutes=self.service.duration_minutes)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client} -> {self.service} ({timezone.localtime(self.start_time).strftime('%d.%m %H:%M')})"
