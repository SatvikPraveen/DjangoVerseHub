# File: DjangoVerseHub/apps/notifications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json

from apps.posts.models import Post, Like
from apps.comments.models import Comment
from apps.accounts.models import Follow
from .models import Notification
from .serializers import NotificationSerializer


@receiver(post_save, sender=Like)
def create_like_notification(sender, instance, created, **kwargs):
    if created and instance.user != instance.post.author:
        notification = Notification.objects.create(
            recipient=instance.post.author,
            sender=instance.user,
            notification_type='like',
            message=f'{instance.user.username} liked your post',
            content_type=ContentType.objects.get_for_model(instance.post),
            object_id=instance.post.id
        )
        send_notification_to_user(notification)


@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    if created and instance.author != instance.post.author:
        notification = Notification.objects.create(
            recipient=instance.post.author,
            sender=instance.author,
            notification_type='comment',
            message=f'{instance.author.username} commented on your post',
            content_type=ContentType.objects.get_for_model(instance.post),
            object_id=instance.post.id
        )
        send_notification_to_user(notification)


@receiver(post_save, sender=Follow)
def create_follow_notification(sender, instance, created, **kwargs):
    if created:
        notification = Notification.objects.create(
            recipient=instance.following,
            sender=instance.follower,
            notification_type='follow',
            message=f'{instance.follower.username} started following you',
        )
        send_notification_to_user(notification)


@receiver(post_save, sender=Post)
def create_post_notification(sender, instance, created, **kwargs):
    if created:
        # Notify followers of new post
        followers = instance.author.followers.all()
        for follow in followers:
            notification = Notification.objects.create(
                recipient=follow.follower,
                sender=instance.author,
                notification_type='post',
                message=f'{instance.author.username} created a new post',
                content_type=ContentType.objects.get_for_model(instance),
                object_id=instance.id
            )
            send_notification_to_user(notification)


def send_notification_to_user(notification):
    """Send real-time notification via WebSocket"""
    channel_layer = get_channel_layer()
    if channel_layer:
        serializer = NotificationSerializer(notification)
        group_name = f'notifications_{notification.recipient.id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_message',
                'notification': serializer.data
            }
        )
        
        # Also send unread count update
        unread_count = Notification.objects.filter(
            recipient=notification.recipient,
            is_read=False
        ).count()
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'unread_count_update',
                'count': unread_count
            }
        )