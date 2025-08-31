# File: DjangoVerseHub/apps/api/routers.py

from rest_framework.routers import DefaultRouter, SimpleRouter
from rest_framework.urlpatterns import format_suffix_patterns
from django.urls import path, include


class CustomDefaultRouter(DefaultRouter):
    """
    Custom router with additional features
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.trailing_slash = '/?'  # Make trailing slash optional

    def get_api_root_view(self, api_urls=None):
        """
        Return a basic root view with custom description
        """
        api_root_dict = {}
        list_name = self.routes[0].name
        for prefix, viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        class APIRootView(self.APIRootView):
            """
            The default basic root view for DefaultRouter
            """
            _ignore_model_permissions = True
            schema = None

            def get_view_name(self):
                return 'DjangoVerseHub API'

            def get_view_description(self, html=False):
                text = """
                Welcome to the DjangoVerseHub API!
                
                This API provides access to:
                - User management and authentication
                - Article CRUD operations
                - Comment system
                - Real-time notifications
                - Search functionality
                
                Authentication is required for most write operations.
                """
                if html:
                    return text.replace('\n', '<br/>')
                return text

        return APIRootView.as_view(api_root_dict=api_root_dict)


class APIRouter:
    """
    Main API router configuration
    """

    def __init__(self):
        self.router = CustomDefaultRouter()
        self.register_viewsets()

    def register_viewsets(self):
        """Register all viewsets with the router"""
        # Import viewsets here to avoid circular imports
        from apps.users.views import UserViewSet, ProfileViewSet
        from apps.articles.views import ArticleViewSet, CategoryViewSet, TagViewSet
        from apps.comments.views import CommentViewSet
        from apps.notifications.views import NotificationViewSet

        # User management
        self.router.register(r'users', UserViewSet, basename='user')
        self.router.register(r'profiles', ProfileViewSet, basename='profile')

        # Content management
        self.router.register(r'articles', ArticleViewSet, basename='article')
        self.router.register(r'categories', CategoryViewSet, basename='category')
        self.router.register(r'tags', TagViewSet, basename='tag')

        # Comments
        self.router.register(r'comments', CommentViewSet, basename='comment')

        # Notifications
        self.router.register(r'notifications', NotificationViewSet, basename='notification')

    def get_urls(self):
        """Get router URLs"""
        return self.router.urls

    def get_api_root_view(self):
        """Get API root view"""
        return self.router.get_api_root_view()


# Create router instance
api_router = APIRouter()


class VersionedRouter:
    """
    Router that supports API versioning
    """

    def __init__(self):
        self.v1_router = CustomDefaultRouter()
        self.register_v1_viewsets()

    def register_v1_viewsets(self):
        """Register v1 viewsets"""
        from apps.users.views import UserViewSet, ProfileViewSet
        from apps.articles.views import ArticleViewSet, CategoryViewSet, TagViewSet
        from apps.comments.views import CommentViewSet
        from apps.notifications.views import NotificationViewSet

        # User management
        self.v1_router.register(r'users', UserViewSet, basename='user')
        self.v1_router.register(r'profiles', ProfileViewSet, basename='profile')

        # Content management
        self.v1_router.register(r'articles', ArticleViewSet, basename='article')
        self.v1_router.register(r'categories', CategoryViewSet, basename='category')
        self.v1_router.register(r'tags', TagViewSet, basename='tag')

        # Comments
        self.v1_router.register(r'comments', CommentViewSet, basename='comment')

        # Notifications
        self.v1_router.register(r'notifications', NotificationViewSet, basename='notification')

    def get_v1_urls(self):
        """Get v1 URLs"""
        return self.v1_router.urls


# Create versioned router instance
versioned_router = VersionedRouter()


class AdminRouter:
    """
    Router for admin-only API endpoints
    """

    def __init__(self):
        self.router = SimpleRouter()
        self.register_admin_viewsets()

    def register_admin_viewsets(self):
        """Register admin viewsets"""
        # Admin-specific viewsets would go here
        pass

    def get_urls(self):
        """Get admin router URLs"""
        return self.router.urls


# Create admin router instance
admin_router = AdminRouter()