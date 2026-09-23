# File: DjangoVerseHub/apps/comments/signals.py

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Comment, CommentLike
from .tasks import moderate_comment, send_comment_like_notification, send_comment_notification


@receiver(post_save, sender=Comment)
def comment_post_save(sender, instance, created, **kwargs):
    """Queue notifications and auto-moderation for a new comment."""
    if not created:
        return

    comment_id = str(instance.id)
    author_id = instance.author_id

    # Collect distinct recipients: the content author and, for a reply, the
    # parent comment's author. Never notify the commenter about their own
    # comment and never send the same person two emails.
    recipients = []  # list of (recipient_id, is_reply)
    seen = {author_id}

    if instance.parent_id and instance.parent.author_id not in seen:
        seen.add(instance.parent.author_id)
        recipients.append((str(instance.parent.author_id), True))

    target = instance.content_object
    target_author_id = getattr(target, 'author_id', None)
    if target_author_id and target_author_id not in seen:
        seen.add(target_author_id)
        recipients.append((str(target_author_id), False))

    def dispatch():
        for recipient_id, is_reply in recipients:
            send_comment_notification.delay(
                comment_id=comment_id,
                recipient_id=recipient_id,
                is_reply=is_reply,
            )
        moderate_comment.delay(comment_id)

    transaction.on_commit(dispatch)


@receiver(post_save, sender=CommentLike)
def comment_like_post_save(sender, instance, created, **kwargs):
    """Increment the denormalised like counter atomically and notify the author."""
    if not created:
        return

    Comment.objects.filter(pk=instance.comment_id).update(likes_count=F('likes_count') + 1)

    comment = instance.comment
    if comment.author_id != instance.user_id:
        comment_id, liker_id = str(comment.id), str(instance.user_id)
        transaction.on_commit(
            lambda: send_comment_like_notification.delay(comment_id=comment_id, liker_id=liker_id)
        )


@receiver(post_delete, sender=CommentLike)
def comment_like_post_delete(sender, instance, **kwargs):
    """Decrement the like counter atomically, never below zero."""
    Comment.objects.filter(
        pk=instance.comment_id, likes_count__gt=0
    ).update(likes_count=F('likes_count') - 1)
