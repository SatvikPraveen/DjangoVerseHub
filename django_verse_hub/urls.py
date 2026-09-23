# File: DjangoVerseHub/django_verse_hub/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django_verse_hub import health

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # Health checks (liveness for the process, readiness for dependencies)
    path("health/", health.readiness, name="health_check"),
    path("health/live/", health.liveness, name="health_live"),
    path("health/ready/", health.readiness, name="health_ready"),
    # Core: home, search, informational pages, sitemap, robots
    path("", include("apps.core.urls")),
    # App URLs
    path("users/", include("apps.users.urls")),
    path("articles/", include("apps.articles.urls")),
    path("comments/", include("apps.comments.urls")),
    path("notifications/", include("apps.notifications.urls")),
    # API URLs
    path("api/v1/", include("apps.api.urls")),
    # Authentication URLs (django-allauth)
    path("accounts/", include("allauth.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Add debug toolbar URLs in development
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns

# Custom error pages
handler400 = "django.views.defaults.bad_request"
handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"
