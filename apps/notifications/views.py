# File: DjangoVerseHub/apps/notifications/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import ListView, UpdateView
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import NotificationPreferenceForm
from .models import NOTIFICATION_TYPES, Notification, NotificationPreference
from .serializers import NotificationPreferenceSerializer, NotificationSerializer

VALID_TYPES = {key for key, _ in NOTIFICATION_TYPES}
STATUS_FILTERS = {"unread", "read"}


def _user_notifications(user):
    """Base queryset: only the requesting user's notifications, list-ready."""
    return Notification.objects.for_user(user).with_related()


def _apply_filters(queryset, params):
    """Shared ?status=unread|read and ?type=<type> filtering for web + API."""
    status_filter = (params.get("status") or "").lower()
    if status_filter == "unread" or (params.get("unread") or "").lower() == "true":
        queryset = queryset.unread()
    elif status_filter == "read":
        queryset = queryset.read()

    type_filter = (params.get("type") or "").lower()
    if type_filter in VALID_TYPES:
        queryset = queryset.of_type(type_filter)
    return queryset


# ---------------------------------------------------------------------------
# Web views
# ---------------------------------------------------------------------------
class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "notifications/notification_list.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return _apply_filters(_user_notifications(self.request.user), self.request.GET)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_filter = (self.request.GET.get("status") or "").lower()
        type_filter = (self.request.GET.get("type") or "").lower()

        # Query string (minus page) so pagination links keep the active filters.
        params = self.request.GET.copy()
        params.pop("page", None)
        querystring = params.urlencode()

        # The unread badge uses `unread_notifications_count` from
        # apps.core.context_processors.notifications (lazy, one query, shared
        # with the navbar) so this view adds no extra COUNT query.
        context.update(
            {
                "notification_types": NOTIFICATION_TYPES,
                "current_status": status_filter if status_filter in STATUS_FILTERS else "",
                "current_type": type_filter if type_filter in VALID_TYPES else "",
                "querystring": f"&{querystring}" if querystring else "",
            }
        )
        return context


@login_required
@require_POST
def mark_all_read_view(request):
    """Non-JS fallback for the 'Mark all read' button on the list page."""
    count = Notification.objects.mark_all_read(request.user)
    messages.success(request, f"{count} notification(s) marked as read.")
    next_url = request.POST.get("next") or reverse("notifications:list")
    if not next_url.startswith("/"):
        next_url = reverse("notifications:list")
    return redirect(next_url)


class NotificationPreferenceView(LoginRequiredMixin, UpdateView):
    """GET renders the preference form; POST saves it."""

    form_class = NotificationPreferenceForm
    template_name = "notifications/preferences.html"
    success_url = reverse_lazy("notifications:preferences")

    def get_object(self, queryset=None):
        return NotificationPreference.for_user(self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Your notification preferences have been saved.")
        return super().form_valid(form)


@login_required
def notifications_websocket_view(request):
    """Live (WebSocket) notification feed page."""
    return render(request, "notifications/notifications_ws.html")


# ---------------------------------------------------------------------------
# JSON API (function views under /notifications/api/)
# ---------------------------------------------------------------------------
class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        response.data["unread_count"] = Notification.objects.unread(self.request.user).count()
        return response


class NotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        return _apply_filters(_user_notifications(self.request.user), self.request.query_params)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark one of the caller's notifications as read (404 for anyone else's)."""
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.mark_as_read()
    return Response(
        {
            "status": "success",
            "unread_count": Notification.objects.unread(request.user).count(),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    count = Notification.objects.mark_all_read(request.user)
    return Response({"status": "success", "marked_count": count, "unread_count": 0})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def unread_count(request):
    return Response({"unread_count": Notification.objects.unread(request.user).count()})


@api_view(["DELETE", "POST"])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete one of the caller's notifications. POST is accepted for HTML forms."""
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    notification.delete()
    return Response(
        {
            "status": "success",
            "unread_count": Notification.objects.unread(request.user).count(),
        }
    )


class NotificationPreferenceAPIView(generics.RetrieveUpdateAPIView):
    """GET / PUT / PATCH the caller's notification preferences."""

    serializer_class = NotificationPreferenceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return NotificationPreference.for_user(self.request.user)


# ---------------------------------------------------------------------------
# DRF router ViewSet (registered by apps.api under /api/v1/notifications/)
# ---------------------------------------------------------------------------
class NotificationViewSet(viewsets.ModelViewSet):
    """
    Notifications of the authenticated user.

    Creation is excluded: notifications are produced by the system.
    Extra routes: mark_read (POST, detail), mark_all_read (POST),
    unread_count (GET), preferences (GET/PUT/PATCH).
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NotificationPagination
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return _apply_filters(_user_notifications(self.request.user), self.request.query_params)

    def create(self, request, *args, **kwargs):
        return Response({"detail": 'Method "POST" not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        """Only `is_read` is client-editable."""
        notification = self.get_object()
        if "is_read" not in request.data:
            return Response({"detail": 'Only "is_read" can be updated.'}, status=status.HTTP_400_BAD_REQUEST)
        if request.data.get("is_read") in (True, "true", "True", 1, "1"):
            notification.mark_as_read()
        else:
            notification.mark_as_unread()
        return Response(self.get_serializer(notification).data)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()
        return Response({"status": "success"})

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        marked = Notification.objects.mark_all_read(request.user)
        return Response({"status": "success", "marked_count": marked})

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        return Response({"unread_count": Notification.objects.unread(request.user).count()})

    @action(detail=False, methods=["get", "put", "patch"])
    def preferences(self, request):
        prefs = NotificationPreference.for_user(request.user)
        if request.method == "GET":
            return Response(NotificationPreferenceSerializer(prefs).data)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=(request.method == "PATCH"))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
