# File: DjangoVerseHub/apps/notifications/consumers.py
"""
WebSocket consumer for real-time notifications.

Each authenticated user joins their personal group ``user_<id>``.

Client -> server messages (JSON):
    {"action": "mark_read", "notification_id": <int>}
    {"action": "mark_all_read"}
    {"action": "get_unread_count"}
    {"action": "ping"}

Server -> client messages (JSON):
    {"type": "notification", "notification": {...}}       new notification
    {"type": "unread_count", "count": <int>}              badge value
    {"type": "notification_read", "notification_id": <int>, "success": <bool>}
    {"type": "all_read", "count": <int>}                  how many were marked
    {"type": "pong"}
    {"type": "error", "message": "..."}
"""

import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from django_verse_hub import metrics

from .models import Notification


def user_group_name(user_id):
    """Channel-layer group that carries one user's notifications."""
    return f"user_{user_id}"


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope.get("user")  # type: ignore[assignment]

        if self.user is None or getattr(self.user, "is_anonymous", True):
            await self.close()
            return

        self.group_name = user_group_name(self.user.pk)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        metrics.websocket_connections.inc()
        await self.accept()

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)
            metrics.websocket_connections.dec()

    # ------------------------------------------------------------------ inbound
    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            payload = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return  # ignore garbage silently; keep the socket open
        if not isinstance(payload, dict):
            return

        action = payload.get("action") or payload.get("type")

        if action == "mark_read":
            notification_id = payload.get("notification_id")
            success = await self.mark_notification_read(notification_id)
            await self.send_json(
                {
                    "type": "notification_read",
                    "notification_id": notification_id,
                    "success": success,
                }
            )
            await self.send_unread_count()

        elif action == "mark_all_read":
            count = await self.mark_all_notifications_read()
            await self.send_json({"type": "all_read", "count": count})
            await self.send_unread_count()

        elif action == "get_unread_count":
            await self.send_unread_count()

        elif action == "ping":
            await self.send_json({"type": "pong"})

    # ----------------------------------------------------------------- outbound
    async def send_json(self, data):
        await self.send(text_data=json.dumps(data))

    async def send_unread_count(self):
        await self.send_json({"type": "unread_count", "count": await self.get_unread_count()})

    # Group event handlers (names match the "type" used in group_send)
    async def notification_message(self, event):
        await self.send_json({"type": "notification", "notification": event["notification"]})

    async def unread_count_update(self, event):
        await self.send_json({"type": "unread_count", "count": event["count"]})

    # ---------------------------------------------------------------- database
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        try:
            notification_id = int(notification_id)
        except (TypeError, ValueError):
            return False
        try:
            notification = Notification.objects.get(pk=notification_id, recipient=self.user)
        except Notification.DoesNotExist:
            return False
        notification.mark_as_read()
        return True

    @database_sync_to_async
    def mark_all_notifications_read(self):
        return Notification.objects.mark_all_read(self.user)

    @database_sync_to_async
    def get_unread_count(self):
        return Notification.objects.unread(self.user).count()
