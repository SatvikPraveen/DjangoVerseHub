# File: DjangoVerseHub/apps/notifications/admin.py
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'recipient', 'sender', 'notification_type', 
        'message_preview', 'is_read', 'created_at'
    ]
    list_filter = [
        'notification_type', 'is_read', 'created_at',
        'content_type'
    ]
    search_fields = [
        'recipient__username', 'sender__username', 
        'message', 'notification_type'
    ]
    readonly_fields = ['created_at', 'read_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('recipient', 'sender', 'notification_type', 'message')
        }),
        ('Related Object', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'created_at', 'read_at')
        }),
    )
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message Preview'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'recipient', 'sender', 'content_type'
        )
    
    actions = ['mark_as_read', 'mark_as_unread']
    
    def mark_as_read(self, request, queryset):
        count = queryset.update(is_read=True)
        self.message_user(request, f'{count} notifications marked as read.')
    mark_as_read.short_description = 'Mark selected notifications as read'
    
    def mark_as_unread(self, request, queryset):
        count = queryset.update(is_read=False)
        self.message_user(request, f'{count} notifications marked as unread.')
    mark_as_unread.short_description = 'Mark selected notifications as unread'