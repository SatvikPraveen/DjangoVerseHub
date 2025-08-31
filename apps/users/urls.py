# File: DjangoVerseHub/apps/users/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'users'

# API router
router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'profiles', views.ProfileViewSet)

urlpatterns = [
    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Profile management
    path('', views.UserListView.as_view(), name='list'),
    path('profile/<uuid:pk>/', views.ProfileDetailView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('settings/', views.profile_settings_view, name='settings'),
    
    # API endpoints
    path('api/', include(router.urls)),
]