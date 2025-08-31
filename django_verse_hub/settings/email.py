# File: DjangoVerseHub/django_verse_hub/settings/email.py

from decouple import config

# Email backend configuration
EMAIL_BACKEND = config(
    'EMAIL_BACKEND', 
    default='django.core.mail.backends.smtp.EmailBackend'
)

# SMTP configuration
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# Email addresses
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@djangoversehub.com')
SERVER_EMAIL = config('SERVER_EMAIL', default='server@djangoversehub.com')

# Email settings for different purposes
EMAIL_ADDRESSES = {
    'NOREPLY': 'noreply@djangoversehub.com',
    'SUPPORT': 'support@djangoversehub.com',
    'ADMIN': 'admin@djangoversehub.com',
    'NOTIFICATIONS': 'notifications@djangoversehub.com',
}

# Email templates
EMAIL_TEMPLATES = {
    'WELCOME': 'emails/welcome.html',
    'PASSWORD_RESET': 'emails/password_reset.html',
    'EMAIL_CONFIRMATION': 'emails/email_confirmation.html',
    'NOTIFICATION': 'emails/notification.html',
    'DAILY_DIGEST': 'emails/daily_digest.html',
    'WEEKLY_SUMMARY': 'emails/weekly_summary.html',
}

# Email subjects
EMAIL_SUBJECTS = {
    'WELCOME': 'Welcome to DjangoVerseHub!',
    'PASSWORD_RESET': 'Reset your password - DjangoVerseHub',
    'EMAIL_CONFIRMATION': 'Confirm your email - DjangoVerseHub',
    'NEW_COMMENT': 'New comment on your article - DjangoVerseHub',
    'ARTICLE_PUBLISHED': 'Your article has been published - DjangoVerseHub',
    'DAILY_DIGEST': 'Your daily digest - DjangoVerseHub',
    'WEEKLY_SUMMARY': 'Weekly summary - DjangoVerseHub',
}

# Email configuration for different environments
if config('DEBUG', default=False, cast=bool):
    # Development email settings
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    EMAIL_FILE_PATH = '/tmp/app-messages'
else:
    # Production email settings
    EMAIL_TIMEOUT = 30
    EMAIL_SSL_KEYFILE = None
    EMAIL_SSL_CERTFILE = None

# Celery email task settings
EMAIL_TASK_CONFIG = {
    'DEFAULT_RETRY_DELAY': 60,
    'MAX_RETRIES': 3,
    'RETRY_BACKOFF': True,
    'RETRY_JITTER': True,
}

# Email rate limiting
EMAIL_RATE_LIMITS = {
    'WELCOME': 1,           # 1 welcome email per user
    'PASSWORD_RESET': 5,    # 5 password reset emails per hour
    'NOTIFICATIONS': 50,    # 50 notification emails per hour per user
    'DIGEST': 1,           # 1 digest email per day per user
}

# Email queue configuration
EMAIL_QUEUES = {
    'HIGH_PRIORITY': 'email_high',
    'NORMAL': 'email_normal',
    'LOW_PRIORITY': 'email_low',
}

# HTML email settings
EMAIL_USE_HTML = True
EMAIL_HTML_TEMPLATE_DIR = 'emails/html/'
EMAIL_TEXT_TEMPLATE_DIR = 'emails/text/'

# Email tracking (if implemented)
EMAIL_TRACKING_ENABLED = config('EMAIL_TRACKING_ENABLED', default=False, cast=bool)
EMAIL_TRACKING_PIXEL = config('EMAIL_TRACKING_PIXEL', default='')

# Mailgun configuration (alternative email service)
MAILGUN_API_KEY = config('MAILGUN_API_KEY', default='')
MAILGUN_DOMAIN = config('MAILGUN_DOMAIN', default='')

# SendGrid configuration (alternative email service)
SENDGRID_API_KEY = config('SENDGRID_API_KEY', default='')

# Amazon SES configuration (alternative email service)
AWS_SES_REGION = config('AWS_SES_REGION', default='us-east-1')
AWS_SES_ACCESS_KEY_ID = config('AWS_SES_ACCESS_KEY_ID', default='')
AWS_SES_SECRET_ACCESS_KEY = config('AWS_SES_SECRET_ACCESS_KEY', default='')