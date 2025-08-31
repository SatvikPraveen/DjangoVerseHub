# File: DjangoVerseHub/apps/comments/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import Comment, CommentLike


class CommentReplyInline(admin.TabularInline):
    """Inline for comment replies"""
    model = Comment
    fk_name = 'parent'
    fields = ['author', 'content', 'is_active', 'is_flagged', 'created_at']
    readonly_fields = ['created_at']
    extra = 0
    show_change_link = True


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin for Comment model"""
    list_display = [
        'content_preview', 'author', 'content_object_link', 'parent_comment',
        'is_active', 'is_flagged', 'is_edited', 'reply_count', 'likes_count',
        'created_at'
    ]
    list_filter = [
        'is_active', 'is_flagged', 'is_edited', 'content_type',
        'created_at', 'updated_at'
    ]
    search_fields = ['content', 'author__email', 'author__first_name', 'author__last_name']
    raw_id_fields = ['author', 'parent']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'content_object_link',
        'thread_info', 'engagement_stats'
    ]
    actions = ['mark_active', 'mark_inactive', 'mark_flagged', 'unflag']
    date_hierarchy = 'created_at'
    inlines = [CommentReplyInline]

    fieldsets = (
        (_('Comment'), {
            'fields': ('author', 'content', 'content_object_link')
        }),
        (_('Threading'), {
            'fields': ('parent', 'thread_info'),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('is_active', 'is_flagged', 'is_edited')
        }),
        (_('Engagement'), {
            'fields': ('engagement_stats',),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def content_preview(self, obj):
        """Show content preview"""
        preview = obj.content[:100]
        if len(obj.content) > 100:
            preview += '...'
        return preview
    content_preview.short_description = _('Content')

    def content_object_link(self, obj):
        """Link to the commented object"""
        if obj.content_object:
            url = reverse(
                f'admin:{obj.content_type.app_label}_{obj.content_type.model}_change',
                args=[obj.object_id]
            )
            return format_html('<a href="{}">{}</a>', url, obj.content_object)
        return '-'
    content_object_link.short_description = _('Content Object')

    def parent_comment(self, obj):
        """Show parent comment if exists"""
        if obj.parent:
            url = reverse('admin:comments_comment_change', args=[obj.parent.pk])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.parent.content[:30] + '...'
            )
        return '-'
    parent_comment.short_description = _('Parent Comment')

    def thread_info(self, obj):
        """Show thread information"""
        depth = obj.get_thread_depth()
        total_replies = obj.total_replies
        return f'Depth: {depth}, Total Replies: {total_replies}'
    thread_info.short_description = _('Thread Info')

    def engagement_stats(self, obj):
        """Show engagement statistics"""
        return f'Likes: {obj.likes_count}, Replies: {obj.reply_count}'
    engagement_stats.short_description = _('Engagement')

    def mark_active(self, request, queryset):
        """Mark selected comments as active"""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} comments marked as active.')
    mark_active.short_description = _('Mark selected comments as active')

    def mark_inactive(self, request, queryset):
        """Mark selected comments as inactive"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} comments marked as inactive.')
    mark_inactive.short_description = _('Mark selected comments as inactive')

    def mark_flagged(self, request, queryset):
        """Flag selected comments"""
        count = queryset.update(is_flagged=True)
        self.message_user(request, f'{count} comments flagged.')
    mark_flagged.short_description = _('Flag selected comments')

    def unflag(self, request, queryset):
        """Unflag selected comments"""
        count = queryset.update(is_flagged=False)
        self.message_user(request, f'{count} comments unflagged.')
    unflag.short_description = _('Unflag selected comments')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'author', 'parent', 'content_type'
        ).prefetch_related('replies')


@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    """Admin for CommentLike model"""
    list_display = ['comment_preview', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['comment__content', 'user__email']
    raw_id_fields = ['comment', 'user']
    readonly_fields = ['created_at']

    def comment_preview(self, obj):
        """Show comment preview"""
        return obj.comment.content[:50] + '...'
    comment_preview.short_description = _('Comment')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('comment', 'user')