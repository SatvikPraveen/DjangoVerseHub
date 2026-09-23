# File: DjangoVerseHub/apps/notifications/apps.py
from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'
    verbose_name = 'Notifications'

    def ready(self):
        # Registers the comment / follow / article receivers.
        from . import signals

        # Like models may not exist (yet); wiring is a no-op until they do.
        try:
            signals.connect_optional_like_signals()
        except Exception:  # pragma: no cover - never block startup
            pass
