# File: DjangoVerseHub/apps/comments/apps.py
from django.apps import AppConfig


class CommentsConfig(AppConfig):
    """
    Django app configuration for the comments application.
    Handles comment functionality including creation, modification, and deletion.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.comments'
    verbose_name = 'Comments'
    
    def ready(self):
        """
        Import signals when the app is ready.
        This ensures that signal handlers are registered when Django starts.
        """
        try:
            import apps.comments.signals
        except ImportError:
            # Handle the case where signals.py doesn't exist yet
            pass