from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class BusinessSignUpForm(forms.Form):
    business_name = forms.CharField(
        label="Business name",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Big Bro Barbershop",
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
        Creates a User, uses email as username,
        and optionally updates Profile.company_name if you use Profile.
        """
        email = self.cleaned_data["email"].lower()
        password = self.cleaned_data["password1"]
        business_name = self.cleaned_data["business_name"]

        user = User.objects.create_user(
            username=email,  # username = email
            email=email,
            password=password,
        )

        # If you have Profile model with company_name & role:
        try:
            profile = user.profile
            profile.company_name = business_name
            profile.role = "provider"
            profile.save()
        except Exception:
            # if no profile model or signal yet, just ignore
            pass

        return user
