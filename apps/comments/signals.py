# File: DjangoVerseHub/apps/comments/signals.py

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import Comment, CommentLike
from .tasks import send_comment_notification, moderate_comment


@receiver(post_save, sender=Comment)
def comment_post_save(sender, instance, created, **kwargs):
    """Handle comment post-save operations"""
    if created:
        # Send notification to content author
        if instance.content_object and hasattr(instance.content_object, 'author'):
            content_author = instance.content_object.author
            if content_author != instance.author:
                send_comment_notification.delay(
                    comment_id=str(instance.id),
                    recipient_id=str(content_author.id)
                )
        
        # Send notification to parent comment author if it's a reply
        if instance.parent and instance.parent.author != instance.author:
            send_comment_notification.delay(
                comment_id=str(instance.id),
                recipient_id=str(instance.parent.author.id),
                is_reply=True
            )
        
        # Auto-moderation for new comments
        moderate_comment.delay(str(instance.id))


@receiver(post_delete, sender=Comment)
def comment_post_delete(sender, instance, **kwargs):
    """Handle comment deletion"""
    # Update parent comment reply count if needed
    if instance.parent:
        # This would be handled by the database CASCADE
        pass
    
    # Clean up any related data
    # CommentLike objects are automatically deleted due to CASCADE


@receiver(post_save, sender=CommentLike)
def comment_like_post_save(sender, instance, created, **kwargs):
    """Handle comment like operations"""
    if created:
        # Update comment likes count
        comment = instance.comment
        comment.likes_count = comment.likes.count()
        comment.save(update_fields=['likes_count'])
        
        # Send notification to comment author
        if comment.author != instance.user:
            from .tasks import send_comment_like_notification
            send_comment_like_notification.delay(
                comment_id=str(comment.id),
                liker_id=str(instance.user.id)
            )


@receiver(post_delete, sender=CommentLike)
def comment_like_post_delete(sender, instance, **kwargs):
    """Handle comment unlike operations"""
    # Update comment likes count
    comment = instance.comment
    comment.likes_count = max(0, comment.likes.count())
    comment.save(update_fields=['likes_count'])