# File: DjangoVerseHub/apps/notifications/tasks.py
"""
Celery tasks for the notifications app.

Referenced by the beat schedule in django_verse_hub/celery.py and
django_verse_hub/settings/celery.py:
    apps.notifications.tasks.send_daily_digest
    apps.notifications.tasks.cleanup_old_notifications
"""
import logging
from collections import defaultdict

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives, send_mail
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


def _site_context():
    return {
        'site_name': getattr(settings, 'SITE_NAME', 'DjangoVerseHub'),
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    }


def _email_allowed(user):
    profile = getattr(user, 'profile', None)
    if profile is not None and not profile.email_notifications:
        return False
    return bool(user.email) and user.is_active


# ---------------------------------------------------------------------------
# Real-time / immediate delivery
# ---------------------------------------------------------------------------
@shared_task(name='apps.notifications.tasks.send_notification', bind=True, max_retries=3)
def send_notification(self, notification_id):
    """Push a single notification over the channel layer."""
    from .models import Notification
    from .signals import send_notification_to_user

    try:
        notification = Notification.objects.select_related('recipient', 'sender').get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.warning('Notification %s no longer exists - skipping', notification_id)
        return False
    try:
        send_notification_to_user(notification)
    except Exception as exc:  # pragma: no cover - send_notification_to_user swallows errors
        logger.exception('Failed to send notification %s', notification_id)
        raise self.retry(countdown=60, exc=exc)
    return True


@shared_task(name='apps.notifications.tasks.send_bulk_notifications')
def send_bulk_notifications(notification_ids):
    """Fan-out: push many notifications by enqueueing one task each."""
    for nid in notification_ids:
        send_notification.delay(nid)
    logger.info('Enqueued %d notification tasks', len(notification_ids))
    return len(notification_ids)


@shared_task(name='apps.notifications.tasks.send_notification_email', bind=True, max_retries=3)
def send_notification_email(self, notification_id):
    """
    Email a single notification immediately.
    Used when the recipient's digest frequency is 'none' and the type allows email.
    """
    from .models import Notification, NotificationPreference

    try:
        notification = Notification.objects.select_related('recipient', 'sender').get(pk=notification_id)
    except Notification.DoesNotExist:
        return False

    user = notification.recipient
    prefs = NotificationPreference.for_user(user)
    if not _email_allowed(user) or not prefs.allows_email(notification.notification_type):
        return False

    context = {
        **_site_context(),
        'recipient': user,
        'notification': notification,
        'title': notification.get_notification_type_display(),
        'message': notification.message,
        'url': _site_context()['site_url'] + notification.url,
    }
    try:
        body = render_to_string('notifications/emails/notification.txt', context)
        send_mail(
            subject=f'[{context["site_name"]}] {notification.message[:80]}',
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception('Failed to email notification %s', notification_id)
        raise self.retry(countdown=60, exc=exc)
    return True


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------
def _send_digest(frequency, hours):
    """
    Email every user who
      - has `frequency` as their digest setting (users without a preference row
        count as 'daily', the model default),
      - allows email at all (Profile.email_notifications, has an address),
      - has unread notifications created in the last `hours` hours of a type
        they want by email.
    Returns the number of digests sent.
    """
    from .models import CONFIGURABLE_TYPES, Notification, NotificationPreference

    since = timezone.now() - timezone.timedelta(hours=hours)
    unread = (
        Notification.objects.unread()
        .filter(created_at__gte=since)
        .select_related('recipient', 'recipient__profile', 'sender', 'content_type')
        .order_by('recipient_id', '-created_at')
    )

    by_user = defaultdict(list)
    for notification in unread:
        by_user[notification.recipient_id].append(notification)
    if not by_user:
        return 0

    prefs_by_user = {
        p.user_id: p
        for p in NotificationPreference.objects.filter(user_id__in=by_user.keys())
    }

    sent = 0
    for user_id, notifications in by_user.items():
        user = notifications[0].recipient
        prefs = prefs_by_user.get(user_id)
        user_frequency = prefs.digest_frequency if prefs else NotificationPreference.DIGEST_DAILY
        if user_frequency != frequency or not _email_allowed(user):
            continue

        wanted_types = set(prefs.email_types()) if prefs else set(CONFIGURABLE_TYPES) | {'system'}
        items = [n for n in notifications if n.notification_type in wanted_types]
        if not items:
            continue

        context = {
            **_site_context(),
            'recipient': user,
            'notifications': items,
            'count': len(items),
            'total_unread': Notification.objects.unread(user).count(),
            'frequency': frequency,
        }
        subject = f'[{context["site_name"]}] Your {frequency} digest: {len(items)} new notification(s)'
        text_body = render_to_string('notifications/emails/digest.txt', context)
        html_body = render_to_string('notifications/emails/digest.html', context)

        try:
            email = EmailMultiAlternatives(
                subject=subject, body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email],
            )
            email.attach_alternative(html_body, 'text/html')
            email.send(fail_silently=False)
            sent += 1
        except Exception:
            logger.exception('Failed to send %s digest to user %s', frequency, user_id)

    logger.info('%s digest sent to %d user(s)', frequency.capitalize(), sent)
    return sent


@shared_task(name='apps.notifications.tasks.send_daily_digest')
def send_daily_digest():
    """Daily digest of the last 24h of unread notifications (Celery beat, daily)."""
    from .models import NotificationPreference

    return _send_digest(NotificationPreference.DIGEST_DAILY, hours=24)


@shared_task(name='apps.notifications.tasks.send_weekly_digest')
def send_weekly_digest():
    """Weekly digest of the last 7 days of unread notifications (add to beat weekly)."""
    from .models import NotificationPreference

    return _send_digest(NotificationPreference.DIGEST_WEEKLY, hours=24 * 7)


# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------
@shared_task(name='apps.notifications.tasks.cleanup_old_notifications')
def cleanup_old_notifications(days=90):
    """
    Delete read notifications older than `days` days (by read_at, falling back
    to created_at for rows marked read before read_at was tracked).
    """
    from .models import Notification

    cutoff = timezone.now() - timezone.timedelta(days=days)
    deleted, _ = (
        Notification.objects.read()
        .filter(Q(read_at__lt=cutoff) | Q(read_at__isnull=True, created_at__lt=cutoff))
        .delete()
    )
    logger.info('Cleaned up %d read notification(s) older than %d days', deleted, days)
    return deleted
