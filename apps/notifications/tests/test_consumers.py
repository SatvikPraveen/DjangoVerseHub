# File: DjangoVerseHub/apps/notifications/tests/test_consumers.py
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase
from django.urls import re_path

from apps.notifications.consumers import NotificationConsumer, user_group_name
from apps.notifications.models import Notification

User = get_user_model()


class NotificationConsumerTest(TransactionTestCase):
    """TransactionTestCase: consumers touch the DB from worker threads, which need committed rows."""

    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@test.com", password="testpass123")
        self.other = User.objects.create_user(username="other", email="other@test.com", password="testpass123")
        self.application = AuthMiddlewareStack(
            URLRouter(  # type: ignore[arg-type]
                [re_path(r"ws/notifications/$", NotificationConsumer.as_asgi())]  # type: ignore[arg-type]
            )
        )

    # ---------------------------------------------------------------- helpers
    async def connect_as(self, user):
        communicator = WebsocketCommunicator(self.application, "ws/notifications/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        return communicator, connected

    async def acreate_notification(self, recipient=None, **kwargs):
        @database_sync_to_async
        def create():
            return Notification.objects.create(
                recipient=recipient or self.user,
                notification_type=kwargs.pop("notification_type", "system"),
                message=kwargs.pop("message", "Test notification"),
                **kwargs,
            )

        return await create()

    # ------------------------------------------------------------------ tests
    async def test_websocket_connect_authenticated(self):
        communicator, connected = await self.connect_as(self.user)
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_websocket_connect_anonymous(self):
        communicator, connected = await self.connect_as(AnonymousUser())
        self.assertFalse(connected)

    async def test_mark_notification_read(self):
        notification = await self.acreate_notification()
        communicator, connected = await self.connect_as(self.user)
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "mark_read", "notification_id": notification.id})

        ack = await communicator.receive_json_from()
        self.assertEqual(ack, {"type": "notification_read", "notification_id": notification.id, "success": True})
        count = await communicator.receive_json_from()
        self.assertEqual(count, {"type": "unread_count", "count": 0})

        await notification.arefresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)
        await communicator.disconnect()

    async def test_cannot_mark_other_users_notification_read(self):
        notification = await self.acreate_notification(recipient=self.other)
        communicator, connected = await self.connect_as(self.user)
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "mark_read", "notification_id": notification.id})
        ack = await communicator.receive_json_from()
        self.assertFalse(ack["success"])

        await notification.arefresh_from_db()
        self.assertFalse(notification.is_read)
        await communicator.disconnect()

    async def test_mark_read_with_garbage_id(self):
        communicator, connected = await self.connect_as(self.user)
        await communicator.send_json_to({"action": "mark_read", "notification_id": "not-an-id"})
        ack = await communicator.receive_json_from()
        self.assertEqual(ack["type"], "notification_read")
        self.assertFalse(ack["success"])
        await communicator.disconnect()

    async def test_mark_all_notifications_read(self):
        notification1 = await self.acreate_notification()
        notification2 = await self.acreate_notification()
        untouched = await self.acreate_notification(recipient=self.other)
        communicator, connected = await self.connect_as(self.user)
        self.assertTrue(connected)

        await communicator.send_json_to({"action": "mark_all_read"})
        ack = await communicator.receive_json_from()
        self.assertEqual(ack, {"type": "all_read", "count": 2})
        count = await communicator.receive_json_from()
        self.assertEqual(count, {"type": "unread_count", "count": 0})

        await notification1.arefresh_from_db()
        await notification2.arefresh_from_db()
        await untouched.arefresh_from_db()
        self.assertTrue(notification1.is_read)
        self.assertTrue(notification2.is_read)
        self.assertFalse(untouched.is_read)
        await communicator.disconnect()

    async def test_get_unread_count(self):
        await self.acreate_notification()
        await self.acreate_notification()
        communicator, _ = await self.connect_as(self.user)
        await communicator.send_json_to({"action": "get_unread_count"})
        self.assertEqual(await communicator.receive_json_from(), {"type": "unread_count", "count": 2})
        await communicator.disconnect()

    async def test_ping_pong(self):
        communicator, _ = await self.connect_as(self.user)
        await communicator.send_json_to({"action": "ping"})
        self.assertEqual(await communicator.receive_json_from(), {"type": "pong"})
        await communicator.disconnect()

    async def test_invalid_json_message(self):
        communicator, connected = await self.connect_as(self.user)
        self.assertTrue(connected)

        await communicator.send_to(text_data="invalid json")
        await communicator.send_json_to(["not", "a", "dict"])
        await communicator.send_json_to({"action": "unknown"})

        # Still alive and silent; a ping proves the socket is still processing.
        self.assertTrue(await communicator.receive_nothing())
        await communicator.send_json_to({"action": "ping"})
        self.assertEqual(await communicator.receive_json_from(), {"type": "pong"})
        await communicator.disconnect()

    def test_group_naming(self):
        self.assertEqual(user_group_name(self.user.pk), f"user_{self.user.pk}")

    async def test_notification_broadcast(self):
        channel_layer = get_channel_layer()
        if not channel_layer:
            self.skipTest("Channel layer not configured")

        communicator, connected = await self.connect_as(self.user)
        self.assertTrue(connected)

        await channel_layer.group_send(
            user_group_name(self.user.pk),
            {"type": "notification_message", "notification": {"id": 1, "message": "Test broadcast notification"}},
        )
        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "notification")
        self.assertEqual(response["notification"]["message"], "Test broadcast notification")

        await channel_layer.group_send(user_group_name(self.user.pk), {"type": "unread_count_update", "count": 7})
        self.assertEqual(await communicator.receive_json_from(), {"type": "unread_count", "count": 7})
        await communicator.disconnect()

    async def test_broadcast_is_per_user(self):
        channel_layer = get_channel_layer()
        if not channel_layer:
            self.skipTest("Channel layer not configured")

        communicator, _ = await self.connect_as(self.user)
        await channel_layer.group_send(
            user_group_name(self.other.pk),
            {"type": "notification_message", "notification": {"id": 2, "message": "Not for you"}},
        )
        self.assertTrue(await communicator.receive_nothing())
        await communicator.disconnect()
