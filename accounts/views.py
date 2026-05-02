import random
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
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
    PasswordVerifyCodeForm,
    PasswordResetSetPasswordForm,
    ProfileUpdateForm
)


from marketplace.forms import WorkingHoursFormSet
from marketplace.models import SalonWorkingHours

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
    if request.user.is_authenticated:
        return redirect("marketplace:home")

    next_url = request.GET.get('next') or request.POST.get('next', '')

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, _("Welcome back! You are now logged in."))
            return redirect(next_url or "marketplace:home")  # ✅ redirect to next
        else:
            messages.error(request, _("Invalid credentials. Please check your username/email and password."))
    else:
        form = AuthenticationForm(request)
        form.fields['username'].label = _("Username or Email")

    return render(request, "accounts/auth_combined.html", {
        "login_form": form,   # ✅ renamed to login_form to match template
        "next": next_url,     # ✅ pass next
    })

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
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')

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

def password_reset_request(request):
    if request.method == 'POST':
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email__iexact=email).first()
            
            if user:
                reset_code = str(random.randint(100000, 999999))
                
                # Calculate expiration time (15 minutes from now)
                expiration = timezone.now() + timezone.timedelta(minutes=15)
                
                # FIX: Add expires_at here
                PasswordResetCode.objects.create(
                    user=user,
                    code=reset_code,
                    expires_at=expiration  # This satisfies the NOT NULL constraint
                )
                
                request.session['reset_email'] = email

                send_mail(
                    subject="Password Reset Code",
                    message=f"Your verification code is: {reset_code}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                )
            
            return redirect('accounts:password_reset_verify')
    else:
        form = PasswordResetRequestForm()

    return render(request, 'accounts/password_reset_request.html', {'form': form})



def password_reset_verify(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('accounts:password_reset_request')

    if request.method == 'POST':
        form = PasswordVerifyCodeForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('code')
            if code_is_valid(email, code): 
                # IMPORTANT: You must pass the email and code in the URL
                return redirect(f"{reverse('accounts:password_reset_confirm')}?email={email}&code={code}")
            else:
                messages.error(request, _("Invalid code. Please try again."))
    else:
        form = PasswordVerifyCodeForm()

    return render(request, 'accounts/password_reset_code.html', {'form': form, 'email': email})


def password_reset_confirm(request):
    # Get identifiers from POST (if form submitted) or GET (if just arrived)
    email = request.POST.get("email") or request.GET.get("email", "")
    code = request.POST.get("code") or request.GET.get("code", "")

    if request.method == "POST":
        form = PasswordResetSetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password1"]
            user = User.objects.filter(email__iexact=email).first()

            if not user:
                messages.error(request, _("User session lost."))
                return redirect("accounts:password_reset_request")

            # Fetch the valid code
            prc = PasswordResetCode.objects.filter(
                user=user,
                code=code,
                used_at__isnull=True
            ).order_by("-created_at").first()

            # Check if it exists and isn't expired
            if prc and not prc.is_expired():
                try:
                    validate_password(new_password, user=user)
                    
                    # SAVE THE NEW PASSWORD
                    user.set_password(new_password)
                    user.save() 

                    # MARK CODE AS USED so it can't be reused
                    prc.used_at = timezone.now()
                    prc.save()

                    # CLEAR SESSION
                    if 'reset_email' in request.session:
                        del request.session['reset_email']

                    messages.success(request, _("Password updated. Please log in."))
                    return redirect("accounts:login_register") # Redirect to your login view
                
                except Exception as e:
                    form.add_error("new_password1", e)
            else:
                messages.error(request, _("Reset code expired or already used."))
                return redirect("accounts:password_reset_request")
    else:
        form = PasswordResetSetPasswordForm(initial={"email": email, "code": code})

    return render(request, "accounts/password_reset_set_password.html", {"form": form})


@login_required
def profile_settings(request):
    profile = request.user.profile

    # Get the first salon owned by the user (assuming 1 salon per user for now)
    salon = request.user.salons.first()

    # Initialize formset and queryset as None — only populated if user has a salon
    hours_formset = None
    hours_qs = None

    if salon:
        # Ensure all 7 days exist in the database for this salon.
        # If any weekday is missing, create it as "closed" by default.
        existing_days = salon.working_hours.values_list('weekday', flat=True)
        for day_num, day_name in SalonWorkingHours.WEEKDAYS:
            if day_num not in existing_days:
                SalonWorkingHours.objects.create(
                    salon=salon,
                    weekday=day_num,
                    is_closed=True,
                )

        # Query the hours for the formset (ordered Monday -> Sunday)
        hours_qs = salon.working_hours.all().order_by('weekday')

    if request.method == 'POST':
        profile_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )

        # Only build the working-hours formset if the user has a salon
        if salon:
            hours_formset = WorkingHoursFormSet(
                request.POST,
                queryset=hours_qs,
                prefix='working_hours',
            )

        # Validate profile form (always) + hours formset (only if salon exists)
        profile_valid = profile_form.is_valid()
        hours_valid = hours_formset.is_valid() if salon else True

        if profile_valid and hours_valid:
            profile_form.save()

            if salon:
                hours_formset.save()

            # Language update logic
            lang = profile_form.cleaned_data.get('language')
            if lang:
                translation.activate(lang)
                request.session['django_language'] = lang

            messages.success(request, _("Settings updated successfully!"))
            return redirect('accounts:settings')
        else:
            messages.error(request, _("Please fix the errors below."))

    else:
        # GET request — build blank/pre-filled forms
        profile_form = ProfileUpdateForm(instance=profile, user=request.user)
        if salon:
            hours_formset = WorkingHoursFormSet(
                queryset=hours_qs,
                prefix='working_hours',
            )

    context = {
        'form': profile_form,
        'salon': salon,
        'hours_formset': hours_formset,
    }
    return render(request, 'accounts/settings.html', context)
