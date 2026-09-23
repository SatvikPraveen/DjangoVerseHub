# File: DjangoVerseHub/apps/comments/apps.py
from django.apps import AppConfig


class CommentsConfig(AppConfig):
    """
    Django app configuration for the comments application.
    Handles comment functionality including creation, modification, and deletion.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.comments"
    verbose_name = "Comments"

    def ready(self):
        """Register signal handlers once the app registry is ready."""
        import apps.comments.signals  # noqa: F401
