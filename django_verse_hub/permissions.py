# File: DjangoVerseHub/django_verse_hub/permissions.py

from django.contrib.auth.mixins import UserPassesTestMixin
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner of the object.
        return obj.author == request.user


class IsAuthorOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow authors of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return hasattr(obj, 'author') and obj.author == request.user


class IsStaffOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow staff users to edit.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.is_authenticated and request.user.is_staff


class IsOwnerMixin(UserPassesTestMixin):
    """
    Mixin to restrict access to object owners only.
    """

    def test_func(self):
        obj = self.get_object()
        return obj.author == self.request.user


class IsStaffMixin(UserPassesTestMixin):
    """
    Mixin to restrict access to staff users only.
    """

    def test_func(self):
        return self.request.user.is_staff


class IsSuperuserMixin(UserPassesTestMixin):
    """
    Mixin to restrict access to superusers only.
    """

    def test_func(self):
        return self.request.user.is_superuser