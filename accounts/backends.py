# accounts/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticates against settings.AUTH_USER_MODEL.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        
        # CHANGE THIS: Use .filter().first() instead of .get()
        user = User.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username)
        ).first()
        
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        # If no user found, run password hasher to prevent timing attacks
        if not user:
            User().set_password(password)
            
        return None