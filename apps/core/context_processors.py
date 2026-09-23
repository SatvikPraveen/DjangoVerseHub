# File: DjangoVerseHub/apps/core/context_processors.py
"""
Template context processors shared by every page.

Everything here must be cheap: it runs on each request. Queries are
deferred through lazy objects so pages that never touch the values
never pay for them.
"""

from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .models import SiteSetting


def site(request):
    """Static site metadata and public site settings."""
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'DjangoVerseHub'),
        'SITE_TAGLINE': getattr(settings, 'SITE_TAGLINE', 'Connect, Learn, Build'),
        'site_settings': SimpleLazyObject(SiteSetting.public_settings),
    }


def notifications(request):
    """Unread count and the five most recent notifications for the navbar."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'unread_notifications_count': 0, 'recent_notifications': []}

    from apps.notifications.models import Notification

    def _unread():
        return Notification.objects.filter(recipient=user, is_read=False).count()

    def _recent():
        return list(
            Notification.objects.filter(recipient=user)
            .select_related('sender')
            .order_by('-created_at')[:5]
        )

    return {
        'unread_notifications_count': SimpleLazyObject(_unread),
        'recent_notifications': SimpleLazyObject(_recent),
    }
