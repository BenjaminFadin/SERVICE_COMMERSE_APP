from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

User = get_user_model()

class UserSignUpForm(forms.Form):
    # CHANGED: Replaced business_name with full_name
    full_name = forms.CharField(
        label="Full Name",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "John Doe",
            }
        ),
    )

    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "you@example.com",
            }
        ),
    )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Create a password",
            }
        ),
        help_text="At least 8 characters, including a number.",
    )

    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Repeat password",
            }
        ),
    )

    accept_terms = forms.BooleanField(
        label="I agree to the Terms and Privacy Policy.",
        required=True,
        widget=forms.CheckboxInput(
            attrs={
                "class": "form-check-input",
                "id": "termsCheck",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")

        if p1 and p2 and p1 != p2:
            raise ValidationError("Passwords do not match.")

        if p1 and len(p1) < 8:
            self.add_error("password1", "Password must be at least 8 characters long.")

        return cleaned_data

    def save(self):
        """
        Creates a User (customer) and updates Profile.full_name.
        """
        email = self.cleaned_data["email"].lower()
        password = self.cleaned_data["password1"]
        full_name = self.cleaned_data["full_name"]

        # 1. Create the User
        user = User.objects.create_user(
            username=email,  # username is the email
            email=email,
            password=password,
        )

        # 2. Update the Profile (created via signals)
        try:
            profile = user.profile
            profile.full_name = full_name
            profile.role = "customer"  # CHANGED: Set role to customer
            profile.save()
        except Exception:
            pass

        return user

class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',       # Adds Bootstrap styling
            'placeholder': 'name@example.com'
        })
    )
class PasswordResetVerifyForm(forms.Form):
    email = forms.EmailField()
    code = forms.CharField(max_length=6)

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError("Enter the 6-digit code.")
        return code

class PasswordResetSetPasswordForm(forms.Form):
    # These must be HiddenInput so the user doesn't see them, 
    # but they MUST be in the form class to be validated.
    email = forms.EmailField(widget=forms.HiddenInput())
    code = forms.CharField(widget=forms.HiddenInput())
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="New Password"
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        label="Confirm Password"
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password1")
        p2 = cleaned_data.get("new_password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError(_("Passwords do not match."))
        return cleaned_data
class PasswordVerifyCodeForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={
            'placeholder': '123456',
            'class': 'form-control text-center letter-spacing-lg',
            'style': 'font-size: 2rem; font-weight: bold;'
        }),
        label=_("Verification Code")
    )