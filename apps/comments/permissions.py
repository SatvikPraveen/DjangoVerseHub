# File: DjangoVerseHub/apps/comments/permissions.py

from rest_framework import permissions


class IsCommentAuthorOrStaff(permissions.BasePermission):
    """
    Object-level permission for comments.

    - update / partial_update: the author (within the edit window) or staff.
    - destroy: the author or staff.
    - everything else (reads, like, flag, stats): any request that passed the
      view-level permission.
    """

    def has_object_permission(self, request, view, obj):
        action = getattr(view, 'action', None)
        if action in ('update', 'partial_update'):
            return obj.can_edit(request.user)
        if action == 'destroy':
            return obj.can_delete(request.user)
        return True
