# File: DjangoVerseHub/apps/notifications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.comments.models import Comment
from .models import Notification
from .serializers import NotificationSerializer


def send_notification_to_user(notification):
    """Send real-time notification via WebSocket channel layer."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        serializer = NotificationSerializer(notification)
        group_name = f'notifications_{notification.recipient.id}'

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': serializer.data,
            },
        )

        unread_count = Notification.objects.filter(
            recipient=notification.recipient,
            is_read=False,
        ).count()

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'unread_count_update',
                'count': unread_count,
            },
        )
    except Exception:
        # Never let a notification delivery failure crash the request cycle.
        pass


@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    When a Comment is created:
      - Notify the content-object author (e.g. the Article author)
      - If it is a reply, also notify the parent comment author.
    """
    if not created:
        return

    sender_display = (
        instance.author.get_full_name() or instance.author.username
    )

    # ── Notify the content-object author ──────────────────────────────────
    if instance.content_object and hasattr(instance.content_object, 'author'):
        content_author = instance.content_object.author
        if content_author != instance.author:
            notification = Notification.objects.create(
                recipient=content_author,
                sender=instance.author,
                notification_type='comment',
                message=f'{sender_display} commented on your article.',
                content_type=ContentType.objects.get_for_model(
                    instance.content_object
                ),
                object_id=str(instance.content_object.pk),
            )
            send_notification_to_user(notification)

    # ── Notify the parent-comment author (reply) ───────────────────────────
    if instance.parent and instance.parent.author != instance.author:
        notification = Notification.objects.create(
            recipient=instance.parent.author,
            sender=instance.author,
            notification_type='comment',
            message=f'{sender_display} replied to your comment.',
            content_type=ContentType.objects.get_for_model(instance),
            object_id=str(instance.pk),
        )
        send_notification_to_user(notification)