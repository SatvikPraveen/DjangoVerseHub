# File: DjangoVerseHub/django_verse_hub/settings/caching.py

from decouple import config

# Redis connection settings
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379')
CACHE_URL = config('CACHE_URL', default='redis://localhost:6379/1')

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': CACHE_URL,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'djangoversehub',
        'VERSION': 1,
        'TIMEOUT': 300,  # 5 minutes
    },
    'sessions': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/2',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'session',
        'TIMEOUT': 86400,  # 24 hours
    },
    'template_cache': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/3',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'template',
        'TIMEOUT': 3600,  # 1 hour
    },
    'api_cache': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f'{REDIS_URL}/4',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'api',
        'TIMEOUT': 900,  # 15 minutes
    },
}

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'
SESSION_COOKIE_AGE = 86400  # 24 hours

# Cache keys
CACHE_KEYS = {
    'ARTICLE_LIST': 'article_list:{page}:{filters}',
    'ARTICLE_DETAIL': 'article_detail:{slug}',
    'USER_PROFILE': 'user_profile:{user_id}',
    'POPULAR_ARTICLES': 'popular_articles:{days}',
    'TRENDING_ARTICLES': 'trending_articles',
    'ARTICLE_COMMENTS': 'article_comments:{article_id}',
    'USER_NOTIFICATIONS': 'user_notifications:{user_id}',
    'NOTIFICATION_COUNT': 'notification_count:{user_id}',
    'SEARCH_RESULTS': 'search:{query}:{page}',
}

# Cache timeouts (in seconds)
CACHE_TIMEOUTS = {
    'SHORT': 300,      # 5 minutes
    'MEDIUM': 3600,    # 1 hour
    'LONG': 86400,     # 24 hours
    'WEEK': 604800,    # 1 week
}

# Cache middleware settings
CACHE_MIDDLEWARE_ALIAS = 'default'
CACHE_MIDDLEWARE_SECONDS = 600  # 10 minutes
CACHE_MIDDLEWARE_KEY_PREFIX = 'middleware'

# View cache decorator timeouts
VIEW_CACHE_TIMEOUTS = {
    'article_list': 600,     # 10 minutes
    'article_detail': 3600,  # 1 hour
    'user_profile': 1800,    # 30 minutes
    'api_endpoints': 300,    # 5 minutes
}

# Template fragment cache timeouts
TEMPLATE_CACHE_TIMEOUTS = {
    'navbar': 3600,          # 1 hour
    'sidebar': 1800,         # 30 minutes
    'footer': 86400,         # 24 hours
    'popular_articles': 3600, # 1 hour
    'user_info': 1800,       # 30 minutes
}