# File: DjangoVerseHub/django_verse_hub/settings/celery.py

from decouple import config
from kombu import Queue, Exchange

# Celery broker configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/2')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/3')

# Celery task settings
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True

# Task routing
CELERY_TASK_ROUTES = {
    'apps.notifications.tasks.send_notification': {'queue': 'notifications'},
    'apps.notifications.tasks.send_bulk_notifications': {'queue': 'notifications'},
    'apps.notifications.tasks.send_daily_digest': {'queue': 'digest'},
    'apps.notifications.tasks.cleanup_old_notifications': {'queue': 'cleanup'},
    'apps.articles.tasks.process_article_images': {'queue': 'media'},
    'apps.articles.tasks.generate_article_preview': {'queue': 'media'},
    'apps.articles.tasks.cleanup_unused_media': {'queue': 'cleanup'},
    'apps.users.tasks.send_welcome_email': {'queue': 'email'},
    'apps.users.tasks.send_password_reset_email': {'queue': 'email'},
    'apps.comments.tasks.send_comment_notification': {'queue': 'notifications'},
}

# Queue configuration
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_QUEUES = (
    Queue('default', Exchange('default'), routing_key='default'),
    Queue('notifications', Exchange('notifications'), routing_key='notifications'),
    Queue('email', Exchange('email'), routing_key='email'),
    Queue('media', Exchange('media'), routing_key='media'),
    Queue('cleanup', Exchange('cleanup'), routing_key='cleanup'),
    Queue('digest', Exchange('digest'), routing_key='digest'),
)

# Worker configuration
CELERY_WORKER_PREFETCH_MULTIPLIER = config('CELERY_WORKER_PREFETCH_MULTIPLIER', default=1, cast=int)
CELERY_WORKER_MAX_TASKS_PER_CHILD = config('CELERY_WORKER_MAX_TASKS_PER_CHILD', default=1000, cast=int)
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Task execution settings
CELERY_TASK_SOFT_TIME_LIMIT = config('CELERY_TASK_SOFT_TIME_LIMIT', default=300, cast=int)  # 5 minutes
CELERY_TASK_TIME_LIMIT = config('CELERY_TASK_TIME_LIMIT', default=600, cast=int)  # 10 minutes
CELERY_TASK_ALWAYS_EAGER = config('CELERY_TASK_ALWAYS_EAGER', default=False, cast=bool)
CELERY_TASK_EAGER_PROPAGATES = True

# Task retry settings
CELERY_TASK_ANNOTATIONS = {
    '*': {
        'rate_limit': '100/m',
        'time_limit': 600,
        'soft_time_limit': 300,
    },
    'apps.notifications.tasks.send_notification': {
        'rate_limit': '50/m',
        'retry_kwargs': {'max_retries': 3, 'countdown': 60},
    },
    'apps.users.tasks.send_welcome_email': {
        'rate_limit': '30/m',
        'retry_kwargs': {'max_retries': 5, 'countdown': 120},
    },
    'apps.articles.tasks.process_article_images': {
        'rate_limit': '10/m',
        'time_limit': 1200,
        'soft_time_limit': 900,
    },
}

# Beat scheduler configuration
CELERY_BEAT_SCHEDULE = {
    'send-daily-digest': {
        'task': 'apps.notifications.tasks.send_daily_digest',
        'schedule': 86400.0,  # 24 hours
        'options': {'queue': 'digest'}
    },
    'cleanup-old-notifications': {
        'task': 'apps.notifications.tasks.cleanup_old_notifications',
        'schedule': 3600.0,  # 1 hour
        'options': {'queue': 'cleanup'}
    },
    'cleanup-unused-media': {
        'task': 'apps.articles.tasks.cleanup_unused_media',
        'schedule': 604800.0,  # 1 week
        'options': {'queue': 'cleanup'}
    },
    'update-trending-articles': {
        'task': 'apps.articles.tasks.update_trending_articles',
        'schedule': 1800.0,  # 30 minutes
        'options': {'queue': 'default'}
    },
}

# Result backend settings
CELERY_RESULT_EXPIRES = 3600  # 1 hour
CELERY_TASK_RESULT_EXPIRES = 3600  # 1 hour
CELERY_RESULT_PERSISTENT = True

# Monitoring and logging
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_SEND_EVENTS = True
CELERY_TASK_TRACK_STARTED = True

# Security
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True

# Redis connection settings
CELERY_REDIS_MAX_CONNECTIONS = 20
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True