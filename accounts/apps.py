from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model

class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from .models import Profile  # local import to avoid circulars

        UserModel = get_user_model()

        def ensure_profile_exists(sender, instance, created, **kwargs):
            if getattr(instance, "_skip_signal_profile", False):
                return
            if created:
                Profile.objects.get_or_create(user=instance)

        post_save.connect(ensure_profile_exists, sender=UserModel, dispatch_uid="ensure_profile_exists")
