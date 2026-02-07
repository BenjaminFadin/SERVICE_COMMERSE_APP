from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile, PasswordResetCode



# ---------------------------------------------------------
# GLOBAL ADMIN SETTINGS (Russian Titles)
# ---------------------------------------------------------
admin.site.site_header = "Администрирование ibron MVP"
admin.site.site_title = "ibron Admin"
admin.site.index_title = "Управление системой"
admin.site.unregister(Group)


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Профиль'

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)
    list_display = ('username', 'email', 'get_role', 'is_staff')
    
    def get_role(self, obj):
        # Check if profile exists to avoid crash if something went wrong
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return "-"
    get_role.short_description = 'Роль'

    # --- FIX START ---
    
    def save_model(self, request, obj, form, change):
        """
        When saving via Admin, tell the Signal to SKIP creating the profile.
        This lets the Inline form create it with the data you entered.
        """
        if not change: # Only on create
            obj._skip_signal_profile = True
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        """
        After the User and Inlines are saved, check if Profile exists.
        If you left the inline fields empty, Django might not have created 
        the profile yet. We force it here.
        """
        super().save_related(request, form, formsets, change)
        
        # If the inline form was empty, no profile exists yet. Create one now.
        if not hasattr(form.instance, 'profile'):
            Profile.objects.create(user=form.instance)

admin.site.register(PasswordResetCode)