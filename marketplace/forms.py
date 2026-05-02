from datetime import datetime

from django import forms
from django.utils import timezone
from django.forms import modelformset_factory

from .models import Master, SalonWorkingHours

from datetime import datetime

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.forms import modelformset_factory

from .models import Master, SalonWorkingHours, BusinessLead


class BookingForm(forms.Form):
    master = forms.ModelChoiceField(queryset=Master.objects.none(), required=False)
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(input_formats=["%H:%M"])
    quantity = forms.IntegerField(
        required=False, min_value=1, initial=1,
        widget=forms.HiddenInput()
    )
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, salon=None, is_pc_club=False, **kwargs):
        super().__init__(*args, **kwargs)

        # basic bootstrap styling
        self.fields["master"].widget.attrs.update({"class": "form-select"})
        self.fields["date"].widget.attrs.update({"class": "form-control"})
        self.fields["comment"].widget.attrs.update({"class": "form-control"})

        self.salon = salon
        self.is_pc_club = is_pc_club
        if salon:
            self.fields["master"].queryset = salon.masters.filter(is_active=True)

        if is_pc_club:
            # Hide master, force quantity required
            self.fields["master"].required = False
            self.fields["master"].widget = forms.HiddenInput()
            self.fields["quantity"].required = True
        else:
            self.fields["master"].required = True

    def clean_quantity(self):
        qty = self.cleaned_data.get("quantity") or 1
        if self.is_pc_club and self.salon:
            total_pcs = self.salon.masters.filter(is_active=True).count()
            if total_pcs == 0:
                raise forms.ValidationError(_("This venue has no PCs configured."))
            if qty < 1 or qty > total_pcs:
                raise forms.ValidationError(
                    _("Quantity must be between 1 and %(n)d.") % {"n": total_pcs}
                )
        return qty

    def build_start_datetime(self):
        d = self.cleaned_data["date"]
        t = self.cleaned_data["time"]
        naive = datetime.combine(d, t)
        return timezone.make_aware(naive, timezone.get_current_timezone())

class SalonWorkingHoursForm(forms.ModelForm):
    open_time = forms.TimeField(
        required=False,
        input_formats=['%H:%M', '%H:%M:%S'],
        widget=forms.TimeInput(
            attrs={
                'type': 'time',
                'class': 'form-control',
                'step': '60',
                'lang': 'ru-RU',
            },
            format='%H:%M',
        ),
    )
    close_time = forms.TimeField(
        required=False,
        input_formats=['%H:%M', '%H:%M:%S'],
        widget=forms.TimeInput(
            attrs={
                'type': 'time',
                'class': 'form-control',
                'step': '60',
                'lang': 'ru-RU',
            },
            format='%H:%M',
        ),
    )

    class Meta:
        model = SalonWorkingHours
        fields = ['weekday', 'is_closed', 'open_time', 'close_time']
        widgets = {
            'weekday': forms.HiddenInput(),
            'is_closed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
        
# This factory creates a group of 7 forms (one for each day)
WorkingHoursFormSet = modelformset_factory(
    SalonWorkingHours,
    form=SalonWorkingHoursForm,
    extra=0,  # No extra empty forms
    can_delete=False
)


class BusinessLeadForm(forms.ModelForm):
    class Meta:
        model = BusinessLead
        fields = ["phone", "description"]
        widgets = {
            "phone": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "+998 90 123 45 67",
                "type": "tel",
                "required": "required",
            }),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Расскажите о вашем бизнесе...",
                "required": "required",
            }),
        }

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        # remove spaces and dashes for length check
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) < 7:
            raise forms.ValidationError("Введите корректный номер телефона.")
        return phone

    def clean_description(self):
        desc = (self.cleaned_data.get("description") or "").strip()
        if len(desc) < 10:
            raise forms.ValidationError("Опишите бизнес подробнее (минимум 10 символов).")
        return desc