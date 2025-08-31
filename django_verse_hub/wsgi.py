# File: DjangoVerseHub/django_verse_hub/wsgi.py

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_verse_hub.settings.prod')

application = get_wsgi_application()