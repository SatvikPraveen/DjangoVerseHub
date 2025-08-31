# File: DjangoVerseHub/django_verse_hub/settings/security.py

from decouple import config

# SSL and HTTPS settings
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS (HTTP Strict Transport Security) settings
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=0, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False, cast=bool)
SECURE_HSTS_PRELOAD = config('SECURE_HSTS_PRELOAD', default=False, cast=bool)

# Content security and XSS protection
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# Referrer policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Cookie security
SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 86400  # 24 hours

CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=False, cast=bool)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# CSRF protection
CSRF_USE_SESSIONS = False
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net",
)
CSP_STYLE_SRC = (
    "'self'",
    "'unsafe-inline'",
    "https://fonts.googleapis.com",
    "https://cdnjs.cloudflare.com",
)
CSP_FONT_SRC = (
    "'self'",
    "https://fonts.gstatic.com",
)
CSP_IMG_SRC = (
    "'self'",
    "data:",
    "https:",
)
CSP_CONNECT_SRC = (
    "'self'",
    "ws:",
    "wss:",
)

# Rate limiting settings
RATELIMIT_ENABLE = config('RATELIMIT_ENABLE', default=True, cast=bool)
RATELIMIT_USE_CACHE = 'default'

# Rate limits for different actions
RATE_LIMITS = {
    'login_attempts': '5/m',      # 5 attempts per minute
    'registration': '3/h',        # 3 registrations per hour
    'password_reset': '5/h',      # 5 password resets per hour
    'api_calls': '1000/h',        # 1000 API calls per hour
    'comment_creation': '10/m',   # 10 comments per minute
    'article_creation': '5/h',    # 5 articles per hour
    'search_queries': '100/h',    # 100 search queries per hour
}

# Security headers
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
}

# File upload security
FILE_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5242880  # 5MB
FILE_UPLOAD_PERMISSIONS = 0o644

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt']

# Content validation
MAX_CONTENT_LENGTH = 10000  # Maximum characters in text fields
MAX_TITLE_LENGTH = 200     # Maximum characters in title fields

# IP-based security
ALLOWED_HOSTS_REGEX = r'^[a-zA-Z0-9.-]+$'
DISALLOWED_IP_RANGES = [
    '192.168.0.0/16',
    '10.0.0.0/8',
    '172.16.0.0/12',
]

# Admin security
ADMIN_URL_REGEX = r'^[a-zA-Z0-9_-]+/$'
ADMIN_SESSION_TIMEOUT = 3600  # 1 hour

# API security
API_KEY_HEADER = 'X-API-Key'
API_SECRET_KEY = config('API_SECRET_KEY', default='')

# Two-factor authentication settings (if implemented)
TWO_FACTOR_ENABLED = config('TWO_FACTOR_ENABLED', default=False, cast=bool)
TWO_FACTOR_CODE_LENGTH = 6
TWO_FACTOR_CODE_TIMEOUT = 300  # 5 minutes

# Account security
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_TIME = 3600    # 1 hour
PASSWORD_RESET_TIMEOUT = 3600  # 1 hour
EMAIL_VERIFICATION_TIMEOUT = 86400  # 24 hours

# Security middleware configuration
SECURITY_MIDDLEWARE_CONFIG = {
    'SECURE_CONTENT_TYPE_NOSNIFF': True,
    'SECURE_BROWSER_XSS_FILTER': True,
    'SECURE_REFERRER_POLICY': 'strict-origin-when-cross-origin',
}