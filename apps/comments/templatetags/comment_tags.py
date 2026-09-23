# File: DjangoVerseHub/apps/comments/templatetags/comment_tags.py
"""
Template tags for rendering comment threads.

Usage in any object's detail template::

    {% load comment_tags %}
    {% render_comments article %}

Renders the whole thread (one query for comments, one for the viewer's
likes) with reply/edit/delete/flag controls and the "[removed]"
placeholders for hidden comments that still have replies.
"""

from django import template
from django.contrib.contenttypes.models import ContentType

from ..models import Comment, CommentLike, build_comment_tree, target_accepts_comments

register = template.Library()


@register.inclusion_tag("comments/comment_tree.html", takes_context=True)
def render_comments(context, obj):
    request = context.get("request")
    user = getattr(request, "user", None)
    # Include hidden comments: those with replies render as "[removed]".
    comments = list(Comment.objects.get_queryset().for_object(obj).with_author())
    roots = build_comment_tree(comments)

    liked_ids = set()
    if user is not None and user.is_authenticated:
        liked_ids = set(
            CommentLike.objects.filter(user=user, comment_id__in=[c.id for c in comments]).values_list(
                "comment_id", flat=True
            )
        )

    return {
        "request": request,
        "user": user,
        "content_object": obj,
        "content_type_id": ContentType.objects.get_for_model(obj).id,
        "comment_nodes": roots,
        "comment_total": sum(1 for c in comments if c.is_active),
        "liked_ids": liked_ids,
        "comments_open": target_accepts_comments(obj),
    }
