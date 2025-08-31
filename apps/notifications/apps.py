# File: DjangoVerseHub/apps/notifications/apps.py
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'

    def ready(self):
        try:
            import apps.notifications.signals
        except ImportError:
            pass