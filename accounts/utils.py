from django.core.cache import cache

def code_is_valid(email, code):
    from .models import PasswordResetCode
    # Check for a matching, unused, and non-expired code for this email
    prc = PasswordResetCode.objects.filter(
        user__email__iexact=email,
        code=code,
        used_at__isnull=True
    ).order_by("-created_at").first()
    
    if prc and not prc.is_expired():
        return True
    return False