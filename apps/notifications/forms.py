# File: DjangoVerseHub/apps/notifications/forms.py
from django import forms

from .models import NotificationPreference


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "in_app_like",
            "in_app_comment",
            "in_app_follow",
            "in_app_mention",
            "in_app_post",
            "email_like",
            "email_comment",
            "email_follow",
            "email_mention",
            "email_post",
            "digest_frequency",
        ]
        widgets = {
            "digest_frequency": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")

    # Convenience groupings for the template.
    def in_app_fields(self):
        return [self[name] for name in self.fields if name.startswith("in_app_")]

    def email_fields(self):
        return [self[name] for name in self.fields if name.startswith("email_")]
