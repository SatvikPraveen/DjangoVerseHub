# File: DjangoVerseHub/apps/articles/apps.py

from django.apps import AppConfig


class ArticlesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.articles'
    verbose_name = 'Articles'

    def ready(self):
        import apps.articles.signals