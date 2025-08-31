# File: DjangoVerseHub/django_verse_hub/celery.py

import os
from celery import Celery
from django.conf import settings

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_verse_hub.settings.dev')

app = Celery('django_verse_hub')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

# Celery beat schedule
app.conf.beat_schedule = {
    'send-daily-digest': {
        'task': 'apps.notifications.tasks.send_daily_digest',
        'schedule': 86400.0,  # 24 hours
    },
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': 3600.0,  # 1 hour
    },
    'cleanup-unused-media': {
        'task': 'apps.articles.tasks.cleanup_unused_media',
        'schedule': 604800.0,  # 1 week
    },
}

app.conf.timezone = 'UTC'

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')