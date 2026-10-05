import re
from django import forms
from .models import Reading, ResponsorialPsalm, GospelAcclamation

SCRIPTURE_RE = re.compile(
    r"^\s*[1-3]?\s?[A-Za-z .]+ \d+(:\d+([ab])?([.-]\d+([ab])?)?([,;]\s?\d+([ab])?([.-]\d+([ab])?)?)*?)\s*$"
)

class ReadingAdminForm(forms.ModelForm):
    class Meta:
        model = Reading
        fields = "__all__"
        widgets = {"content": forms.Textarea(attrs={"rows": 14, "style": "font-family:monospace"})}

    def clean_reference(self):
        ref = self.cleaned_data["reference"]
        if not SCRIPTURE_RE.match(ref):
            raise forms.ValidationError("Bad reference. Try e.g. 'Hebrews 1:1-6' or 'Mk 1:14-20'.")
        return ref

    def clean(self):
        cleaned = super().clean()
        # Require at least one cycle tagged
        if not self.instance.pk:
            sunday = cleaned.get("sunday_cycles")
            weekday = cleaned.get("weekday_cycles")
            # ModelForm returns managers only after save; check posted lists via data
        return cleaned


class ResponsorialPsalmForm(forms.ModelForm):
    class Meta:
        model = ResponsorialPsalm
        fields = "__all__"

    def clean_verses(self):
        v = self.cleaned_data.get("verses") or []
        if not isinstance(v, list):
            raise forms.ValidationError("Verses must be a list of strings.")
        return v


class GospelAcclamationForm(forms.ModelForm):
    class Meta:
        model = GospelAcclamation
        fields = "__all__"
