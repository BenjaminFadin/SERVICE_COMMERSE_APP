from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Category, Salon, Master, Service, Appointment, SalonWorkingHours, SalonPhoto

# 2. Marketplace Admin
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    # CHANGED: 'name' -> 'name_ru'
    list_display = ('name_ru', 'slug')
    # CHANGED: 'name' -> 'name_ru' (Generate slug from Russian name)
    prepopulated_fields = {'slug': ('name_ru',)}

class ServiceInline(admin.TabularInline):
    model = Service
    extra = 1

class MasterInline(admin.TabularInline):
    model = Master
    extra = 1

@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    # CHANGED: 'name' -> 'name_ru'
    list_display = ('name_ru', 'name_uz', 'name_en', 'owner', 'city_display', 'phone', 'category')
    # CHANGED: 'name' -> 'name'
    search_fields = ('name', 'owner__email', 'phone')
    list_filter = ('category',)
    inlines = [MasterInline, ServiceInline]

    def city_display(self, obj):
        return obj.address[:30] + "..." if obj.address else "-"
    city_display.short_description = "Адрес"

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('client', 'get_service', 'master', 'start_time', 'status')
    list_filter = ('status', 'start_time', 'salon')
    search_fields = ('client__email', 'client__username', 'id')
    date_hierarchy = 'start_time'

    # Helper to prevent errors if Service name is looked up incorrectly
    def get_service(self, obj):
        return obj.service.name_ru if obj.service else "-"
    get_service.short_description = "Услуга"
    

@admin.register(SalonWorkingHours)
class SalonWorkingHoursAdmin(admin.ModelAdmin):
    # CHANGED: 'name' -> 'name_ru'
    list_display = ('salon', 'weekday', 'is_closed', 'open_time', 'close_time')
    search_fields = ('salon__name_ru',)
    list_filter = ('salon',)

admin.site.register(SalonPhoto)