from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile



# ---------------------------------------------------------
# GLOBAL ADMIN SETTINGS (Russian Titles)
# ---------------------------------------------------------
admin.site.site_header = "Администрирование Booksy MVP"
admin.site.site_title = "Booksy Admin"
admin.site.index_title = "Управление системой"
admin.site.unregister(Group)


# 1. Custom User & Profile Admin
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Профиль'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'get_role', 'is_staff')
    
    def get_role(self, obj):
        return obj.profile.get_role_display()
    get_role.short_description = 'Роль'
