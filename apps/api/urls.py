# File: DjangoVerseHub/apps/api/urls.py

from django.urls import path, include
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from .routers import api_router, versioned_router, admin_router
from . import views

app_name = 'api'

# Schema view for API documentation
schema_view = get_schema_view(
    openapi.Info(
        title="DjangoVerseHub API",
        default_version='v1',
        description="""
        A comprehensive API for the DjangoVerseHub platform.
        
        ## Authentication
        
        The API supports multiple authentication methods:
        - **Token Authentication**: Include `Authorization: Token <your-token>` header
        - **Session Authentication**: Use Django's session authentication
        
        ## Rate Limiting
        
        API endpoints are rate limited:
        - Anonymous users: 100 requests per hour
        - Authenticated users: 1000 requests per hour
        - Staff users: 5000 requests per hour
        
        ## Endpoints
        
        - `/users/` - User management
        - `/articles/` - Article CRUD operations
        - `/comments/` - Comment system
        - `/categories/` - Article categories
        - `/tags/` - Article tags
        - `/notifications/` - User notifications
        - `/search/` - Global search
        - `/stats/` - Platform statistics
        
        ## Pagination
        
        List endpoints support pagination with these parameters:
        - `page` - Page number (default: 1)
        - `page_size` - Items per page (default: 20, max: 100)
        
        ## Filtering and Searching
        
        Many endpoints support filtering and search:
        - `search` - Search in relevant fields
        - `ordering` - Order results by field (prefix with `-` for descending)
        - Field-specific filters as documented in each endpoint
        """,
        terms_of_service="https://djangoversehub.com/terms/",
        contact=openapi.Contact(email="api@djangoversehub.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

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
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema_swagger_ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema_redoc'),
    path('schema.json', schema_view.without_ui(cache_timeout=0), name='schema_json'),
    path('schema.yaml', schema_view.without_ui(cache_timeout=0), name='schema_yaml'),
]

# Add version-specific URLs
v1_patterns = [
    path('', views.api_root, name='v1_api_root'),
    path('health/', views.health_check, name='v1_health_check'),
    path('stats/', views.api_stats, name='v1_api_stats'),
    path('auth/login/', views.LoginAPIView.as_view(), name='v1_auth_login'),
    path('auth/logout/', views.LogoutAPIView.as_view(), name='v1_auth_logout'),
    path('auth/token/', obtain_auth_token, name='v1_auth_token'),
    path('search/', views.SearchAPIView.as_view(), name='v1_search'),
    path('dashboard/', views.user_dashboard, name='v1_user_dashboard'),
    path('trending/', views.TrendingContentAPIView.as_view(), name='v1_trending'),
    path('', include(versioned_router.get_v1_urls())),
]

# Version-specific URL patterns
urlpatterns += [
    path('v1/', include((v1_patterns, 'v1'), namespace='v1')),
]