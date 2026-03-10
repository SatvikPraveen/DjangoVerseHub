# File: DjangoVerseHub/apps/notifications/tasks.py
"""
Celery tasks for the notifications app.
These tasks are referenced by name in settings/celery.py beat schedules.
"""

import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name='apps.notifications.tasks.send_notification', bind=True, max_retries=3)
def send_notification(self, notification_id):
    """Send a single notification (email + WebSocket) to a user."""
    from .models import Notification
    from .signals import send_notification_to_user

    try:
        notification = Notification.objects.select_related('recipient', 'sender').get(pk=notification_id)
        send_notification_to_user(notification)
        logger.info(f'Notification {notification_id} sent to {notification.recipient}')
    except Notification.DoesNotExist:
        logger.warning(f'Notification {notification_id} no longer exists — skipping')
    except Exception as exc:
        logger.exception(f'Failed to send notification {notification_id}')
        raise self.retry(countdown=60, exc=exc)


@shared_task(name='apps.notifications.tasks.send_bulk_notifications', bind=True)
def send_bulk_notifications(self, notification_ids):
    """Fan-out: send multiple notifications by enqueueing individual tasks."""
    for nid in notification_ids:
        send_notification.delay(nid)
    logger.info(f'Enqueued {len(notification_ids)} notification tasks')


@shared_task(name='apps.notifications.tasks.send_daily_digest')
def send_daily_digest():
    """
    Send a daily digest email to users who have unread notifications.
    Runs once per day via Celery beat.
    """
    from .models import Notification
    from django.core.mail import send_mail
    from django.conf import settings

    cutoff = timezone.now() - timezone.timedelta(hours=24)
    recipients = (
        Notification.objects.filter(is_read=False, created_at__gte=cutoff)
        .values_list('recipient_id', flat=True)
        .distinct()
    )

    sent = 0
    for user_id in recipients:
        try:
            user = User.objects.get(pk=user_id)
            unread = Notification.objects.filter(recipient=user, is_read=False).count()
            send_mail(
                subject=f'You have {unread} unread notification(s) — DjangoVerseHub',
                message=(
                    f'Hi {user.get_full_name() or user.username},\n\n'
                    f'You have {unread} unread notification(s) on DjangoVerseHub.\n\n'
                    'Log in to check them out!'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            sent += 1
        except User.DoesNotExist:
            pass

    logger.info(f'Daily digest sent to {sent} user(s)')
    return sent


@shared_task(name='apps.notifications.tasks.cleanup_old_notifications')
def cleanup_old_notifications(days=90):
    """
    Delete read notifications older than `days` days.
    Runs periodically via Celery beat to keep the notifications table lean.
    """
    from .models import Notification

    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = Notification.objects.filter(is_read=True, created_at__lt=cutoff).delete()
    logger.info(f'Cleaned up {deleted} old notification(s) (older than {days} days)')
    return deleted
