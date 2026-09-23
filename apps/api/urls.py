# File: DjangoVerseHub/apps/api/urls.py

from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView, TokenBlacklistView
from rest_framework import permissions
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from .routers import api_router, versioned_router, admin_router
from . import views

app_name = 'api'

urlpatterns = [
    # API root
    path('', views.api_root, name='api_root'),
    
    # Health and stats
    path('health/', views.health_check, name='health_check'),
    path('stats/', views.api_stats, name='api_stats'),
    
    # Authentication
    path('auth/login/', views.LoginAPIView.as_view(), name='auth_login'),
    path('auth/logout/', views.LogoutAPIView.as_view(), name='auth_logout'),
    path('auth/token/', obtain_auth_token, name='auth_token'),
    path('auth/jwt/create/', TokenObtainPairView.as_view(), name='jwt_create'),
    path('auth/jwt/refresh/', TokenRefreshView.as_view(), name='jwt_refresh'),
    path('auth/jwt/verify/', TokenVerifyView.as_view(), name='jwt_verify'),
    path('auth/jwt/blacklist/', TokenBlacklistView.as_view(), name='jwt_blacklist'),
    
    # Search
    path('search/', views.SearchAPIView.as_view(), name='search'),
    
    # Dashboard
    path('dashboard/', views.user_dashboard, name='user_dashboard'),
    
    # Trending content
    path('trending/', views.TrendingContentAPIView.as_view(), name='trending'),
    
    # Main API routes (v1)
    path('', include(versioned_router.get_v1_urls())),
    
    # Admin API routes
    path('admin/', include(admin_router.get_urls())),
    
    # API Documentation
    # OpenAPI 3 schema and interactive docs (drf-spectacular)
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='schema_swagger_ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='schema_redoc'),
]
