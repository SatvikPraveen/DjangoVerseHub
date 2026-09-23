# File: DjangoVerseHub/apps/comments/admin.py

from django.contrib import admin
from django.db.models import Count
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Comment, CommentFlag, CommentLike


class CommentReplyInline(admin.TabularInline):
    """Inline for comment replies"""

    model = Comment
    fk_name = "parent"
    fields = ["author", "content", "is_active", "is_flagged", "created_at"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["author"]
    extra = 0
    show_change_link = True


class CommentFlagInline(admin.TabularInline):
    """Reports filed against this comment"""

    model = CommentFlag
    fields = ["user", "reason", "details", "created_at"]
    readonly_fields = ["user", "reason", "details", "created_at"]
    extra = 0
    can_delete = True


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Admin for Comment model"""

    list_display = [
        "content_preview",
        "author",
        "content_object_link",
        "parent_comment",
        "depth",
        "is_active",
        "is_flagged",
        "flag_count",
        "is_edited",
        "likes_count",
        "created_at",
    ]
    list_filter = ["is_active", "is_flagged", "is_edited", "content_type", "created_at"]
    search_fields = ["content", "author__email", "author__username", "author__first_name", "author__last_name"]
    raw_id_fields = ["author", "parent"]
    readonly_fields = [
        "id",
        "depth",
        "likes_count",
        "created_at",
        "updated_at",
        "content_object_link",
        "thread_info",
    ]
    actions = ["approve_comments", "hide_comments", "mark_flagged", "unflag"]
    date_hierarchy = "created_at"
    inlines = [CommentFlagInline, CommentReplyInline]

    fieldsets = (
        (_("Comment"), {"fields": ("author", "content", "content_object_link")}),
        (_("Threading"), {"fields": ("parent", "depth", "thread_info"), "classes": ("collapse",)}),
        (_("Status"), {"fields": ("is_active", "is_flagged", "is_edited")}),
        (_("Engagement"), {"fields": ("likes_count",), "classes": ("collapse",)}),
        (_("Metadata"), {"fields": ("id", "created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("author", "parent", "content_type")
            .annotate(_flag_count=Count("flags", distinct=True))
        )

    @admin.display(description=_("Content"))
    def content_preview(self, obj):
        return obj.content[:100] + ("..." if len(obj.content) > 100 else "")

    @admin.display(description=_("Content Object"))
    def content_object_link(self, obj):
        target = obj.content_object
        if target is None:
            return "-"
        try:
            url = reverse(
                f"admin:{obj.content_type.app_label}_{obj.content_type.model}_change",
                args=[obj.object_id],
            )
        except NoReverseMatch:
            return str(target)
        return format_html('<a href="{}">{}</a>', url, target)

    @admin.display(description=_("Parent Comment"))
    def parent_comment(self, obj):
        if not obj.parent_id:
            return "-"
        url = reverse("admin:comments_comment_change", args=[obj.parent_id])
        return format_html('<a href="{}">{}</a>', url, obj.parent.content[:30] + "...")

    @admin.display(description=_("Flags"), ordering="_flag_count")
    def flag_count(self, obj):
        return getattr(obj, "_flag_count", None) or obj.flags.count()

    @admin.display(description=_("Thread Info"))
    def thread_info(self, obj):
        return f"Depth: {obj.depth}, Direct replies: {obj.reply_count}, Total replies: {obj.total_replies}"

    @admin.action(description=_("Approve selected comments (show and clear flags)"))
    def approve_comments(self, request, queryset):
        count = queryset.update(is_active=True, is_flagged=False)
        CommentFlag.objects.filter(comment__in=queryset).delete()
        self.message_user(request, f"{count} comments approved.")

    @admin.action(description=_("Hide selected comments"))
    def hide_comments(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"{count} comments hidden.")

    @admin.action(description=_("Flag selected comments"))
    def mark_flagged(self, request, queryset):
        count = queryset.update(is_flagged=True)
        self.message_user(request, f"{count} comments flagged.")

    @admin.action(description=_("Unflag selected comments"))
    def unflag(self, request, queryset):
        count = queryset.update(is_flagged=False)
        self.message_user(request, f"{count} comments unflagged.")


@admin.register(CommentFlag)
class CommentFlagAdmin(admin.ModelAdmin):
    list_display = ["comment_preview", "user", "reason", "created_at"]
    list_filter = ["reason", "created_at"]
    search_fields = ["comment__content", "user__email", "details"]
    raw_id_fields = ["comment", "user"]
    readonly_fields = ["created_at"]

    @admin.display(description=_("Comment"))
    def comment_preview(self, obj):
        return obj.comment.content[:50]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("comment", "user")


@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    """Admin for CommentLike model"""

    list_display = ["comment_preview", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["comment__content", "user__email"]
    raw_id_fields = ["comment", "user"]
    readonly_fields = ["created_at"]

    @admin.display(description=_("Comment"))
    def comment_preview(self, obj):
        return obj.comment.content[:50]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("comment", "user")
