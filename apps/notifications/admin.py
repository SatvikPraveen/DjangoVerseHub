# File: DjangoVerseHub/apps/notifications/admin.py
from django.contrib import admin
from django.utils import timezone

from .models import Notification, NotificationPreference


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'sender', 'notification_type', 'message_preview', 'is_read', 'created_at']
    list_filter = ['notification_type', 'is_read', 'created_at', 'content_type']
    search_fields = ['recipient__username', 'recipient__email', 'sender__username', 'message']
    readonly_fields = ['created_at', 'read_at']
    raw_id_fields = ['recipient', 'sender']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    list_select_related = ['recipient', 'sender', 'content_type']

    fieldsets = (
        ('Basic Info', {'fields': ('recipient', 'sender', 'notification_type', 'message')}),
        ('Related Object', {'fields': ('content_type', 'object_id'), 'classes': ('collapse',)}),
        ('Status', {'fields': ('is_read', 'created_at', 'read_at')}),
    )

    actions = ['mark_as_read', 'mark_as_unread']

    @admin.display(description='Message')
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message

    @admin.action(description='Mark selected notifications as read')
    def mark_as_read(self, request, queryset):
        count = queryset.filter(is_read=False).update(is_read=True, read_at=timezone.now())
        self.message_user(request, f'{count} notifications marked as read.')

    @admin.action(description='Mark selected notifications as unread')
    def mark_as_unread(self, request, queryset):
        count = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f'{count} notifications marked as unread.')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'digest_frequency', 'in_app_comment', 'email_comment', 'updated_at']
    list_filter = ['digest_frequency']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']
    list_select_related = ['user']
