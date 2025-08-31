# File: DjangoVerseHub/django_verse_hub/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import JsonResponse

def health_check(request):
    """Simple health check endpoint"""
    return JsonResponse({'status': 'ok', 'message': 'DjangoVerseHub is running'})

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Health check
    path('health/', health_check, name='health_check'),
    
    # Home page
    path('', TemplateView.as_view(template_name='base.html'), name='home'),
    
    # App URLs
    path('users/', include('apps.users.urls')),
    path('articles/', include('apps.articles.urls')),
    path('comments/', include('apps.comments.urls')),
    path('notifications/', include('apps.notifications.urls')),
    
    # API URLs
    path('api/v1/', include('apps.api.urls')),
    
    # Authentication URLs (django-allauth)
    path('accounts/', include('allauth.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Add debug toolbar URLs in development
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

# Custom error pages
handler400 = 'django.views.defaults.bad_request'
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'