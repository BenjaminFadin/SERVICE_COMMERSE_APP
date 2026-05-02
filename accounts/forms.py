from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import Profile

User = get_user_model()

class UserSignUpForm(forms.Form):
    first_name = forms.CharField(
        label="First Name",
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "John",
                "required": "required",
            }
        ),
    )

    last_name = forms.CharField(
        label="Last Name",
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Doe",
                "required": "required",
            }
        ),
    )

    phone_number = forms.CharField(
        label="Phone Number",
        max_length=30,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "+998 90 123 45 67",
                "type": "tel",
                "required": "required",
            }
        ),
    )

    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "you@example.com",
                "required": "required",
            }
        ),
    )

    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Create a password",
                "required": "required",
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
                "required": "required",
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
        Creates a User (customer) and updates Profile with name + phone.
        """
        email = self.cleaned_data["email"].lower()
        password = self.cleaned_data["password1"]
        first_name = self.cleaned_data["first_name"]
        last_name = self.cleaned_data["last_name"]
        phone_number = self.cleaned_data["phone_number"]

        # 1. Create the User
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        # 2. Update the Profile (created via signals)
        try:
            profile = user.profile
            profile.full_name = f"{first_name} {last_name}".strip()
            profile.phone = phone_number
            profile.role = "customer"
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



class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)

    class Meta:
        model = Profile
        fields = [
            'avatar', 'phone', 'gender', 'language',
            'telegram_id', 'bio', 'company_name', 'website'
        ]


    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Apply Bootstrap classes to all fields
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control rounded-pill'})
        
        # Special styling for Textarea
        if 'bio' in self.fields:
            self.fields['bio'].widget.attrs.update({'class': 'form-control rounded-4', 'rows': 3})

        # Gender uses a select widget — needs form-select instead of form-control
        if 'gender' in self.fields:
            self.fields['gender'].widget.attrs.update({'class': 'form-select rounded-pill'})
            self.fields['gender'].required = False

        # --- SET INITIAL VALUES FROM USER OBJECT ---
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        
        # Update User model fields
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            profile.save()
        return profile