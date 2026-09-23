# File: DjangoVerseHub/apps/core/admin.py

from django.contrib import admin
from django.utils import timezone

from .models import ContactMessage, NewsletterSubscriber, SiteSetting


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "user", "is_confirmed", "confirmed_at", "unsubscribed_at", "created_at")
    list_filter = ("is_confirmed",)
    search_fields = ("email", "user__email", "user__username")
    readonly_fields = ("confirmation_token", "created_at", "updated_at")
    actions = ["confirm_selected", "unsubscribe_selected"]

    @admin.action(description="Mark selected as confirmed")
    def confirm_selected(self, request, queryset):
        now = timezone.now()
        queryset.update(is_confirmed=True, confirmed_at=now, unsubscribed_at=None)

    @admin.action(description="Unsubscribe selected")
    def unsubscribe_selected(self, request, queryset):
        queryset.update(unsubscribed_at=timezone.now())


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("subject", "kind", "status", "name", "email", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("subject", "message", "name", "email")
    readonly_fields = ("ip_address", "user_agent", "created_at", "updated_at", "resolved_at")
    actions = ["mark_resolved", "mark_spam"]

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        queryset.update(status=ContactMessage.Status.RESOLVED, resolved_at=timezone.now())

    @admin.action(description="Mark selected as spam")
    def mark_spam(self, request, queryset):
        queryset.update(status=ContactMessage.Status.SPAM)


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "is_public", "updated_at")
    list_filter = ("is_public",)
    search_fields = ("key", "description")
