# File: DjangoVerseHub/apps/comments/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'comments'

# API router
router = DefaultRouter()
router.register(r'comments', views.CommentViewSet, basename='comment')

urlpatterns = [
    # Web views
    path('', views.CommentListView.as_view(), name='list'),
    path('create/', views.CommentCreateView.as_view(), name='create'),
    path('<uuid:pk>/edit/', views.CommentUpdateView.as_view(), name='edit'),
    path('<uuid:pk>/delete/', views.CommentDeleteView.as_view(), name='delete'),
    
    # AJAX views
    path('<uuid:comment_id>/reply/', views.comment_reply_view, name='reply'),
    path('<uuid:comment_id>/like/', views.comment_like_view, name='like'),
    path('<uuid:comment_id>/flag/', views.comment_flag_view, name='flag'),
    
    # API endpoints
    path('api/', include(router.urls)),
]