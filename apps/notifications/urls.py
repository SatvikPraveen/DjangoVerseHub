# File: DjangoVerseHub/apps/notifications/urls.py
from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    # Web views
    path('', views.NotificationListView.as_view(), name='list'),
    path('websocket/', views.notifications_websocket_view, name='websocket'),
    
    # API endpoints
    path('api/', views.NotificationListAPIView.as_view(), name='api_list'),
    path('api/<int:notification_id>/read/', views.mark_notification_read, name='api_mark_read'),
    path('api/read-all/', views.mark_all_notifications_read, name='api_mark_all_read'),
    path('api/unread-count/', views.unread_count, name='api_unread_count'),
    path('api/<int:notification_id>/delete/', views.delete_notification, name='api_delete'),
]