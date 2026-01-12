from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
import secrets
import string
from datetime import timedelta

@receiver(post_save, sender=User)
def ensure_profile_exists(sender, instance, created, **kwargs):
    # 1. Check if we set a flag to skip this signal (used by Admin)
    if getattr(instance, '_skip_signal_profile', False):
        return

    # 2. Standard logic: Create profile if it doesn't exist
    if created:
        Profile.objects.get_or_create(user=instance)

class User(AbstractUser):
    # Optional extra fields directly on user
    email = models.EmailField(null=True, blank=True)
    # Example: force login by email later if you want
    REQUIRED_FIELDS = ["email"]
    
    def __str__(self):
        return self.username or self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    telegram_id = models.CharField(max_length=50, null=True, blank=True)
    # ---- Basic fields for service-offering app ----
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # Example: role can be "customer" / "provider"
    ROLE_CHOICES = (
        ("customer", "Customer"),
        ("provider", "Service Provider"),
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="customer",
    )

    # For providers: short description, etc.
    bio = models.TextField(blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    website = models.URLField(blank=True)

    # Common stuff
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.username
        

# -----------------------------
# Password reset by 6-digit code
# -----------------------------


class PasswordResetCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="password_reset_codes")

    # store code as string so leading zeros are kept
    code = models.CharField(max_length=6)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    used_at = models.DateTimeField(blank=True, null=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=["user", "code"]),
            models.Index(fields=["expires_at"]),
        ]

    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    def is_used(self) -> bool:
        return self.used_at is not None

    @staticmethod
    def generate_code() -> str:
        # 6-digit numeric code
        return "".join(secrets.choice(string.digits) for _ in range(6))

    @classmethod
    def create_for_user(cls, user, ttl_minutes: int = 10):
        # Optional: invalidate previous unused codes
        cls.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())

        code = cls.generate_code()
        now = timezone.now()
        return cls.objects.create(
            user=user,
            code=code,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )


# ---- Signals so Profile is auto-created/updated ----

# @receiver(post_save, sender=User)
# def ensure_profile_exists(sender, instance, created, **kwargs):
#     """
#     Always ensure a Profile exists for the User.
#     Safe for admin, creates only if missing.
#     """
#     Profile.objects.get_or_create(user=instance)

# @receiver(post_save, sender=User)
# def save_user_profile(sender, instance, **kwargs):
#     instance.profile.save()