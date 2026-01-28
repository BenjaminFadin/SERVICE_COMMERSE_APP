from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from mptt.admin import DraggableMPTTAdmin
from .models import Category, Salon, Master, Service, Appointment, SalonWorkingHours, SalonPhoto


class ParentCategoryFilter(admin.SimpleListFilter):
    title = 'Parent Category' # The name displayed in the filter sidebar
    parameter_name = 'parent_cat' # The URL parameter

    def lookups(self, request, model_admin):
        # Only show categories that have no parent (the root nodes)
        parents = Category.objects.filter(parent__isnull=True)
        return [(p.id, p.name_ru) for p in parents]

    def queryset(self, request, queryset):
        # If a parent is selected, filter salons that belong to 
        # that parent OR any of its subcategories
        if self.value():
            parent_category = Category.objects.get(id=self.value())
            # get_descendants(include_self=True) handles the MPTT logic
            descendants = parent_category.get_descendants(include_self=True)
            return queryset.filter(category__in=descendants)
        return queryset

# 2. Marketplace Admin
@admin.register(Category)
class CategoryAdmin(DraggableMPTTAdmin):
    # This provides a drag-and-drop interface and clear hierarchy
    mptt_level_indent = 20
    list_display = (
        'tree_actions',
        'indented_title',
        'slug',
        'icon_class',
    )
    list_display_links = ('indented_title',)
    prepopulated_fields = {"slug": ("name_ru",)} # Useful for auto-generating slugs
    
class ServiceInline(admin.TabularInline):
    model = Service
    extra = 1

class MasterInline(admin.TabularInline):
    model = Master
    extra = 1

@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'city_display', 'phone', 'category')
    search_fields = ('name', 'owner__email', 'phone')
    
    # Use the custom filter class here
    list_filter = (ParentCategoryFilter, 'category') 
    
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