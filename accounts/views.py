import random
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.contrib import messages
from django.utils.translation import gettext as _
from django.conf import settings
from django.core.cache import cache
from django.utils import translation
from django.views.decorators.http import require_POST
from .utils import code_is_valid
from .forms import UserSignUpForm
from .forms import (
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    PasswordVerifyCodeForm,
    PasswordResetSetPasswordForm,
)
from .models import PasswordResetCode


User = get_user_model()


@require_POST
def set_language(request):
    lang = request.POST.get("language")
    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "/")

    if lang not in dict(settings.LANGUAGES):
        return redirect(next_url)

    # Store in session for anonymous users too
    request.session["django_language"] = lang
    
    # Store in profile for logged-in users
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile:
            profile.language = lang
            profile.save(update_fields=["language"])

    response = redirect(next_url)

    # Optional but good: set cookie used by LocaleMiddleware
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang,
        max_age=365 * 24 * 60 * 60,
        samesite="Lax",
    )
    return response


# Need add profile settings page, password reset using email also

def login_view(request):
    if request.method == "POST":
        # We pass request data to the form
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "You are now logged in.")
            return redirect("marketplace:home") # Ensure this URL pattern exists
        else:
            # If invalid, we fall through to render the template with form errors
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/auth_combined.html", {"form": form})


def logout_view(request):
    # If you want logout only via POST (more secure):
    # if request.method == "POST":
    #     logout(request)
    # else:
    #     return redirect("home")

    logout(request)  # logs out current user
    return redirect('marketplace:home')

def auth_view(request):
    # Initialize forms
    login_form = AuthenticationForm()
    register_form = UserSignUpForm() # CHANGED: Use User form
    
    active_section = 'login'

    if request.method == "POST":
        # --- LOGIN LOGIC ---
        if 'login_submit' in request.POST:
            active_section = 'login'
            login_form = AuthenticationForm(request, data=request.POST)
            if login_form.is_valid():
                user = login_form.get_user()
                login(request, user)
                # messages.success(request, "You are now logged in.")
                return redirect("marketplace:home")
            else:
                messages.error(request, "Invalid username or password.")

        # --- REGISTER LOGIC (User) ---
        elif 'register_submit' in request.POST:
            active_section = 'register'
            # CHANGED: Use UserSignUpForm
            register_form = UserSignUpForm(request.POST) 
            if register_form.is_valid():
                user = register_form.save()
                login(request, user)
                # messages.success(request, "Account created! Welcome.")
                return redirect("marketplace:home")
            else:
                messages.error(request, "Registration failed. Please fix the errors.")

    context = {
        "login_form": login_form,
        "register_form": register_form,
        "active_section": active_section, 
    }
    return render(request, "accounts/auth_combined.html", context)


# PASSWORD RESET VIEWS TO BE ADDED HERE
def password_reset_request(request):
    if request.method == 'POST':
        # 2. Bind the POST data to the form
        form = PasswordResetRequestForm(request.POST)
        
        if form.is_valid():
            # Get the validated email
            email = form.cleaned_data['email']
            
            # --- Logic to generate/send code ---
            reset_code = str(random.randint(100000, 999999))
            cache.set(f"reset_code_{email}", reset_code, timeout=600)
            request.session['reset_email'] = email

            send_mail(
                subject="Password Reset Code",
                message=f"Your verification code is: {reset_code}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )
            # -----------------------------------

            return redirect('accounts:password_reset_verify')
    
    else:
        # 3. GET request: Create an empty form so the field shows up
        form = PasswordResetRequestForm()

    # 4. Pass 'form' to the template context
    return render(request, 'accounts/password_reset_request.html', {'form': form})

def password_reset_verify(request):
    # Retrieve email from session set in the previous email-entry step
    email = request.session.get('reset_email')
    
    if not email:
        return redirect('accounts:password_reset_request')

    if request.method == 'POST':
        form = PasswordVerifyCodeForm(request.POST)
        if form.is_post():
            code = form.cleaned_data.get('code')
            # Add your logic to check if 'code' matches the one sent to 'email'
            if code_is_valid(email, code): 
                return redirect('accounts:password_reset_confirm')
            else:
                messages.error(request, _("Invalid code. Please try again."))
    else:
        form = PasswordVerifyCodeForm()

    return render(request, 'accounts/password_reset_code.html', {
        'form': form,
        'email': email
    })

def password_reset_set_password(request):
    """
    Step 3: user sets new password using email+code.
    """
    initial = {
        "email": request.GET.get("email", ""),
        "code": request.GET.get("code", ""),
    }

    if request.method == "POST":
        form = PasswordResetSetPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            code = form.cleaned_data["code"]
            new_password = form.cleaned_data["new_password1"]

            user = User.objects.filter(email__iexact=email).first()
            if not user:
                messages.error(request, "Invalid email or code.")
                return render(request, "accounts/password_reset_set_password.html", {"form": form})

            prc = PasswordResetCode.objects.filter(
                user=user,
                code=code,
                used_at__isnull=True,
            ).order_by("-created_at").first()

            if not prc or prc.is_expired():
                messages.error(request, "Invalid or expired code. Request a new one.")
                return redirect("accounts:password_reset_request")

            # Validate password via Django validators
            try:
                validate_password(new_password, user=user)
            except Exception as e:
                # e is ValidationError; show messages
                form.add_error("new_password1", e)
                return render(request, "accounts/password_reset_set_password.html", {"form": form})

            user.set_password(new_password)
            user.save(update_fields=["password"])

            prc.used_at = timezone.now()
            prc.save(update_fields=["used_at"])

            messages.success(request, "Password updated. You can now log in.")
            return redirect("accounts:login")  # adjust to your login url name
    else:
        form = PasswordResetSetPasswordForm(initial=initial)

    return render(request, "accounts/password_reset_set_password.html", {"form": form})
