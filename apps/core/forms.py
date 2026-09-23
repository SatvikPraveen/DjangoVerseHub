# File: DjangoVerseHub/apps/core/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage, NewsletterSubscriber


class HoneypotMixin(forms.Form):
    """Invisible field that bots fill in and humans never see."""

    website_url = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'tabindex': '-1', 'class': 'd-none'}),
        label='',
    )

    def clean_website_url(self):
        if self.cleaned_data.get('website_url'):
            raise forms.ValidationError(_('Spam detected.'))
        return ''


class ContactForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'subject', 'message']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Your name')}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('you@example.com')}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        }

    kind = ContactMessage.Kind.CONTACT

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None and user.is_authenticated:
            self.fields['name'].initial = user.get_full_name() or user.username
            self.fields['email'].initial = user.email

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if len(message) < 10:
            raise forms.ValidationError(_('Please provide a little more detail (at least 10 characters).'))
        return message

    def save(self, commit=True, request=None):
        instance = super().save(commit=False)
        instance.kind = self.kind
        if self.user is not None and self.user.is_authenticated:
            instance.user = self.user
        if request is not None:
            instance.ip_address = _client_ip(request)
            instance.user_agent = request.META.get('HTTP_USER_AGENT', '')[:300]
        if commit:
            instance.save()
        return instance


class FeedbackForm(ContactForm):
    kind = ContactMessage.Kind.FEEDBACK


class NewsletterSignupForm(HoneypotMixin, forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': _('you@example.com')})
    )

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def save(self, user=None):
        """Create or re-activate a subscriber. Returns (subscriber, created)."""
        email = self.cleaned_data['email']
        subscriber, created = NewsletterSubscriber.objects.get_or_create(email=email)
        changed = False
        if user is not None and user.is_authenticated and subscriber.user_id is None:
            subscriber.user = user
            changed = True
        if subscriber.unsubscribed_at is not None:
            subscriber.unsubscribed_at = None
            changed = True
        if changed:
            subscriber.save()
        return subscriber, created


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
