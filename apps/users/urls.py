# File: DjangoVerseHub/apps/users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'users'

# API router
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'profiles', views.ProfileViewSet, basename='profile')

urlpatterns = [
    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Profile management
    path('', views.UserListView.as_view(), name='list'),
    path('leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    path('following/', views.following_view, name='following'),
    path('activity/', views.activity_view, name='activity'),
    path('profile/<uuid:pk>/', views.ProfileDetailView.as_view(), name='profile'),
    path('profile/<uuid:pk>/follow/', views.follow_view, name='follow'),
    path('profile/<uuid:pk>/unfollow/', views.unfollow_view, name='unfollow'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('settings/', views.profile_settings_view, name='settings'),

    # API endpoints
    path('api/', include(router.urls)),
]
