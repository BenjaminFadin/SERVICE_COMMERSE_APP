from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

# ==========================================
# 1. HELPER MIXIN (To save code repetition)
# ==========================================
class MultilingualMixin(models.Model):
    """
    Abstract class to add 3 language support to any model.
    Assumes the model will have name_ru, name_en, name_uz.
    """
    class Meta:
        abstract = True

    def get_name_in_language(self, lang_code):
        if lang_code == 'en':
            return getattr(self, 'name_en', '') or self.name_ru
        elif lang_code == 'uz':
            return getattr(self, 'name_uz', '') or self.name_ru
        return self.name_ru

# ==========================================
# 2. MARKETPLACE MODELS
# ==========================================

class Category(MultilingualMixin, models.Model):
    # Russian (Default)
    name_ru = models.CharField(max_length=100, verbose_name="Название (RU)")
    # English
    name_en = models.CharField(max_length=100, blank=True, verbose_name="Название (EN)")
    # Uzbek
    name_uz = models.CharField(max_length=100, blank=True, verbose_name="Название (UZ)")
    
    slug = models.SlugField(unique=True, verbose_name="URL метка")
    icon = models.ImageField(upload_to="categories/", blank=True, null=True, verbose_name="Иконка")

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name_ru


class Salon(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='salons', verbose_name="Владелец")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='salons', verbose_name="Категория")
    
    # Name in 3 languages
    name_ru = models.CharField(max_length=200, verbose_name="Название салона (RU)")
    name_en = models.CharField(max_length=200, blank=True, verbose_name="Название салона (EN)")
    name_uz = models.CharField(max_length=200, blank=True, verbose_name="Название салона (UZ)")

    # Description in 3 languages
    description_ru = models.TextField(blank=True, verbose_name="Описание (RU)")
    description_en = models.TextField(blank=True, verbose_name="Описание (EN)")
    description_uz = models.TextField(blank=True, verbose_name="Описание (UZ)")

    address = models.TextField(verbose_name="Адрес")
    phone = models.CharField(max_length=20, verbose_name="Телефон салона")
    logo = models.ImageField(upload_to="salon_logos/", blank=True, null=True, verbose_name="Логотип")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"

    def __str__(self):
        return self.name_ru


class Service(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services', verbose_name="Салон")
    
    # Service Name in 3 languages
    name_ru = models.CharField(max_length=200, verbose_name="Название услуги (RU)")
    name_en = models.CharField(max_length=200, blank=True, verbose_name="Название услуги (EN)")
    name_uz = models.CharField(max_length=200, blank=True, verbose_name="Название услуги (UZ)")
    
    # Description in 3 languages
    description_ru = models.TextField(blank=True, verbose_name="Описание (RU)")
    description_en = models.TextField(blank=True, verbose_name="Описание (EN)")
    description_uz = models.TextField(blank=True, verbose_name="Описание (UZ)")

    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    duration_minutes = models.PositiveIntegerField(verbose_name="Длительность (мин)")
    
    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"

    def __str__(self):
        return f"{self.name_ru} - {self.price}"


class Master(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='masters', verbose_name="Салон")
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='master_profile')
    
    # Names usually don't need translation, but Specialization does
    name = models.CharField(max_length=100, verbose_name="Имя мастера")
    
    specialization_ru = models.CharField(max_length=100, verbose_name="Специализация (RU)", blank=True)
    specialization_en = models.CharField(max_length=100, verbose_name="Специализация (EN)", blank=True)
    specialization_uz = models.CharField(max_length=100, verbose_name="Специализация (UZ)", blank=True)

    photo = models.ImageField(upload_to="masters/", blank=True, null=True, verbose_name="Фото")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"

    def __str__(self):
        return self.name
    
class Appointment(models.Model):
    """The booking event linking Client, Master, and Service"""
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

    def save(self, *args, **kwargs):
        # Auto-calculate end_time based on service duration
        if self.start_time and self.service and not self.end_time:
            from datetime import timedelta
            self.end_time = self.start_time + timedelta(minutes=self.service.duration_minutes)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.client} -> {self.service} ({self.start_time.strftime('%d.%m %H:%M')})"