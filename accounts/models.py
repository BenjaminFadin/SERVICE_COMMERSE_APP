from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    # Optional extra fields directly on user
    email = models.EmailField(null=True, blank=True)
    # Example: force login by email later if you want
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return self.username or self.email


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

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
        

# ---- Signals so Profile is auto-created/updated ----

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
