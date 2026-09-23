# File: DjangoVerseHub/apps/notifications/urls.py
from django.urls import path

from . import views

app_name = "notifications"

# Notification.pk is a BigAutoField, so `<int:...>` converters are correct here.
urlpatterns = [
    # Web views
    path("", views.NotificationListView.as_view(), name="list"),
    path("mark-all-read/", views.mark_all_read_view, name="mark_all_read"),
    path("preferences/", views.NotificationPreferenceView.as_view(), name="preferences"),
    path("websocket/", views.notifications_websocket_view, name="websocket"),
    # JSON API used by the templates / notifications.js
    path("api/", views.NotificationListAPIView.as_view(), name="api_list"),
    path("api/<int:notification_id>/read/", views.mark_notification_read, name="api_mark_read"),
    path("api/<int:notification_id>/delete/", views.delete_notification, name="api_delete"),
    path("api/read-all/", views.mark_all_notifications_read, name="api_mark_all_read"),
    path("api/unread-count/", views.unread_count, name="api_unread_count"),
    path("api/preferences/", views.NotificationPreferenceAPIView.as_view(), name="api_preferences"),
]
