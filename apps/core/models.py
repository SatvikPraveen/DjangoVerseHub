# File: DjangoVerseHub/apps/core/models.py
"""
Site-wide models that do not belong to a single domain app:
newsletter subscriptions, contact/feedback messages and simple
key/value site settings.
"""

import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    """Abstract base with created/updated timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NewsletterSubscriber(TimeStampedModel):
    """Double opt-in newsletter subscription."""

    email = models.EmailField(_("email address"), unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="newsletter_subscriptions",
    )
    is_confirmed = models.BooleanField(_("confirmed"), default=False)
    confirmation_token = models.CharField(max_length=64, unique=True, editable=False)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_newsletter_subscriber"
        verbose_name = _("newsletter subscriber")
        verbose_name_plural = _("newsletter subscribers")
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        if not self.confirmation_token:
            self.confirmation_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def is_active(self):
        return self.is_confirmed and self.unsubscribed_at is None

    def confirm(self):
        self.is_confirmed = True
        self.confirmed_at = timezone.now()
        self.unsubscribed_at = None
        self.save(update_fields=["is_confirmed", "confirmed_at", "unsubscribed_at", "updated_at"])

    def unsubscribe(self):
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["unsubscribed_at", "updated_at"])


class ContactMessage(TimeStampedModel):
    """Messages submitted through the contact and feedback forms."""

    class Kind(models.TextChoices):
        CONTACT = "contact", _("Contact")
        FEEDBACK = "feedback", _("Feedback")
        BUG = "bug", _("Bug report")
        ABUSE = "abuse", _("Abuse report")

    class Status(models.TextChoices):
        NEW = "new", _("New")
        IN_PROGRESS = "in_progress", _("In progress")
        RESOLVED = "resolved", _("Resolved")
        SPAM = "spam", _("Spam")

    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.CONTACT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField(max_length=5000)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="contact_messages",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_contact_message"
        verbose_name = _("contact message")
        verbose_name_plural = _("contact messages")
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.get_kind_display()}] {self.subject}"

    def mark_resolved(self):
        self.status = self.Status.RESOLVED
        self.resolved_at = timezone.now()
        self.save(update_fields=["status", "resolved_at", "updated_at"])


class SiteSetting(TimeStampedModel):
    """
    Editable key/value settings (feature flags, banners, limits) that
    operators can change from the admin without a deploy.
    """

    key = models.SlugField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True)
    is_public = models.BooleanField(
        default=False,
        help_text=_("Public settings are exposed to templates and the API."),
    )

    class Meta:
        db_table = "core_site_setting"
        ordering = ["key"]

    def __str__(self):
        return self.key

    CACHE_KEY = "core:site_settings:public"

    @classmethod
    def public_settings(cls):
        """Return public settings as a dict, cached for five minutes."""
        from django.core.cache import cache

        data = cache.get(cls.CACHE_KEY)
        if data is None:
            data = dict(cls.objects.filter(is_public=True).values_list("key", "value"))
            cache.set(cls.CACHE_KEY, data, 300)
        return data

    def save(self, *args, **kwargs):
        from django.core.cache import cache

        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)
