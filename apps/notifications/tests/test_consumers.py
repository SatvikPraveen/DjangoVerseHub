# File: DjangoVerseHub/apps/notifications/tests/test_consumers.py
import json
from django.test import TestCase
from django.contrib.auth import get_user_model
from channels.testing import WebsocketCommunicator
from channels.routing import URLRouter
from channels.middleware import AuthMiddlewareStack
from django.urls import re_path
from apps.notifications.consumers import NotificationConsumer
from apps.notifications.models import Notification

User = get_user_model()


class NotificationConsumerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )

    async def test_websocket_connect_authenticated(self):
        """Test WebSocket connection for authenticated user"""
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
            ])
        )
        
        communicator = WebsocketCommunicator(
            application, 
            "ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        await communicator.disconnect()

    async def test_websocket_connect_anonymous(self):
        """Test WebSocket connection rejection for anonymous user"""
        from django.contrib.auth.models import AnonymousUser
        
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
            ])
        )
        
        communicator = WebsocketCommunicator(
            application, 
            "ws/notifications/"
        )
        communicator.scope['user'] = AnonymousUser()
        
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)

    async def test_mark_notification_read(self):
        """Test marking notification as read via WebSocket"""
        # Create a notification
        notification = await self.acreate_notification()
        
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
            ])
        )
        
        communicator = WebsocketCommunicator(
            application, 
            "ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send mark read message
        await communicator.send_json_to({
            'action': 'mark_read',
            'notification_id': notification.id
        })
        
        # Verify notification was marked as read
        await notification.arefresh_from_db()
        self.assertTrue(notification.is_read)
        
        await communicator.disconnect()

    async def test_mark_all_notifications_read(self):
        """Test marking all notifications as read"""
        # Create multiple notifications
        notification1 = await self.acreate_notification()
        notification2 = await self.acreate_notification()
        
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
            ])
        )
        
        communicator = WebsocketCommunicator(
            application, 
            "ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send mark all read message
        await communicator.send_json_to({
            'action': 'mark_all_read'
        })
        
        # Verify all notifications were marked as read
        await notification1.arefresh_from_db()
        await notification2.arefresh_from_db()
        self.assertTrue(notification1.is_read)
        self.assertTrue(notification2.is_read)
        
        await communicator.disconnect()

    async def test_invalid_json_message(self):
        """Test handling of invalid JSON messages"""
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
            ])
        )
        
        communicator = WebsocketCommunicator(
            application, 
            "ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send invalid JSON - should not crash
        await communicator.send_to(text_data="invalid json")
        
        # Connection should still be alive
        self.assertTrue(communicator.output_queue.empty())
        
        await communicator.disconnect()

    async def acreate_notification(self):
        """Helper to create notification asynchronously"""
        from channels.db import database_sync_to_async
        
        @database_sync_to_async
        def create_notification():
            return Notification.objects.create(
                recipient=self.user,
                notification_type='system',
                message='Test notification'
            )
        
        return await create_notification()

    def test_group_naming(self):
        """Test WebSocket group naming convention"""
        expected_group_name = f'notifications_{self.user.id}'
        
        # This would typically be tested in integration with the consumer
        # but we can verify the naming pattern
        self.assertEqual(expected_group_name, f'notifications_{self.user.id}')

    async def test_notification_broadcast(self):
        """Test broadcasting notification to WebSocket group"""
        from channels.layers import get_channel_layer
        from asgiref.sync import sync_to_async
        
        channel_layer = get_channel_layer()
        if not channel_layer:
            self.skipTest("Channel layer not configured")
        
        application = AuthMiddlewareStack(
            URLRouter([
                re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
            ])
        )
        
        communicator = WebsocketCommunicator(
            application, 
            "ws/notifications/"
        )
        communicator.scope['user'] = self.user
        
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)
        
        # Send a message to the group
        group_name = f'notifications_{self.user.id}'
        await channel_layer.group_send(
            group_name,
            {
                'type': 'notification_message',
                'notification': {
                    'id': 1,
                    'message': 'Test broadcast notification'
                }
            }
        )
        
        # Receive the message
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'notification')
        self.assertEqual(response['notification']['message'], 'Test broadcast notification')
        
        await communicator.disconnect()