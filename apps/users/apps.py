# File: DjangoVerseHub/apps/users/apps.py

from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "User Management"

    def ready(self):
        """Import signals when app is ready"""
        from . import signals  # noqa: F401
