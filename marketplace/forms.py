from django import forms
from django.utils import timezone
from datetime import datetime
from .models import Appointment, Master


class BookingForm(forms.Form):
    master = forms.ModelChoiceField(queryset=Master.objects.none())
    date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}))
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        if salon:
            self.fields["master"].queryset = salon.masters.filter(is_active=True)

    def build_start_datetime(self):
        tz = timezone.get_current_timezone()
        d = self.cleaned_data["date"]
        t = self.cleaned_data["time"]
        return timezone.make_aware(datetime.combine(d, t), tz)
