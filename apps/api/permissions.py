# File: DjangoVerseHub/apps/api/permissions.py

from rest_framework import permissions
from rest_framework.permissions import BasePermission


class IsOwnerOrReadOnly(BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    Assumes the model instance has an `author` attribute.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        return obj.author == request.user


class IsAuthorOrReadOnly(BasePermission):
    """
    Custom permission to only allow authors of an object to edit it.
    More flexible than IsOwnerOrReadOnly.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the author
        return hasattr(obj, 'author') and obj.author == request.user


class IsStaffOrReadOnly(BasePermission):
    """
    Custom permission to only allow staff users to edit.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        return request.user.is_authenticated and request.user.is_staff


class IsVerifiedUser(BasePermission):
    """
    Custom permission to only allow verified users.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            hasattr(request.user, 'is_verified') and 
            request.user.is_verified
        )


class IsOwnerOrStaff(BasePermission):
    """
    Custom permission to allow owners or staff to access object.
    """

    def has_object_permission(self, request, view, obj):
        # Staff users can access any object
        if request.user.is_staff:
            return True
        
        # Owners can access their own objects
        return obj.author == request.user


class CanCreateArticle(BasePermission):
    """
    Permission to check if user can create articles.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check if user is verified
        if hasattr(request.user, 'is_verified') and not request.user.is_verified:
            return False
        
        return True


class CanCreateComment(BasePermission):
    """
    Permission to check if user can create comments.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Optionally check if user is verified for commenting
        return True


class IsProfileOwner(BasePermission):
    """
    Permission to check if user owns the profile.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions for anyone
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for profile owner
        return obj.user == request.user


class CanModerateContent(BasePermission):
    """
    Permission for content moderation.
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.is_superuser)
        )


class APIKeyPermission(BasePermission):
    """
    Permission class for API key authentication.
    """

    def has_permission(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return False
        
        # Here you would validate the API key
        # For now, just check if it exists
        from django.conf import settings
        valid_keys = getattr(settings, 'API_KEYS', [])
        return api_key in valid_keys


class RateLimitPermission(BasePermission):
    """
    Permission class that implements rate limiting.
    """

    def has_permission(self, request, view):
        from django.core.cache import cache
        from django.conf import settings
        
        if not hasattr(settings, 'API_RATE_LIMIT'):
            return True
        
        # Get user identifier
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
        else:
            identifier = f"ip:{request.META.get('REMOTE_ADDR')}"
        
        # Check rate limit
        cache_key = f"rate_limit:{identifier}"
        current_count = cache.get(cache_key, 0)
        
        rate_limit = settings.API_RATE_LIMIT.get('requests_per_hour', 1000)
        
        if current_count >= rate_limit:
            return False
        
        # Increment counter
        cache.set(cache_key, current_count + 1, 3600)  # 1 hour
        return True