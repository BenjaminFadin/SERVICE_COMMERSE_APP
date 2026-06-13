from django.contrib import admin
from .models import PCClub, PCPlan, PCAddress, PCWorkingHours, PCBooking


class PCPlanInline(admin.TabularInline):
    model = PCPlan
    extra = 1
    fields = ('name', 'price_per_hour', 'color', 'icon_class', 'sort_order', 'is_active')


class PCAddressInline(admin.StackedInline):
    model = PCAddress
    extra = 0


class PCWorkingHoursInline(admin.TabularInline):
    model = PCWorkingHours
    extra = 0


@admin.register(PCClub)
class PCClubAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'category', 'phone', 'total_pcs', 'created_at')
    list_filter = ('category',)
    search_fields = ('name', 'address', 'phone')
    inlines = [PCPlanInline, PCAddressInline, PCWorkingHoursInline]


@admin.register(PCPlan)
class PCPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'pc_club', 'price_per_hour', 'color', 'sort_order', 'is_active')
    list_filter = ('pc_club', 'is_active')


@admin.register(PCBooking)
class PCBookingAdmin(admin.ModelAdmin):
    list_display = ('client', 'pc_club', 'plan', 'quantity', 'hours', 'start_time', 'status')
    list_filter = ('status', 'pc_club')
    search_fields = ('client__username',)
