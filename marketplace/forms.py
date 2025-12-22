from datetime import datetime

from django import forms
from django.utils import timezone

from .models import Master


class BookingForm(forms.Form):
    master = forms.ModelChoiceField(queryset=Master.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(input_formats=["%H:%M"])

    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)

        # basic bootstrap styling
        self.fields["master"].widget.attrs.update({"class": "form-select"})
        self.fields["date"].widget.attrs.update({"class": "form-control"})
        self.fields["comment"].widget.attrs.update({"class": "form-control"})

        self.salon = salon
        if salon:
            self.fields["master"].queryset = salon.masters.filter(is_active=True)

    def build_start_datetime(self):
        d = self.cleaned_data["date"]
        t = self.cleaned_data["time"]
        naive = datetime.combine(d, t)
        return timezone.make_aware(naive, timezone.get_current_timezone())
