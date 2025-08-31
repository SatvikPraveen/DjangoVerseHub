# File: DjangoVerseHub/apps/notifications/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from apps.notifications.models import Notification
from apps.posts.models import Post

User = get_user_model()


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@test.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@test.com',
            password='testpass123'
        )
        self.post = Post.objects.create(
            author=self.user1,
            content='Test post content'
        )

    def test_notification_creation(self):
        """Test basic notification creation"""
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='like',
            message='user2 liked your post'
        )
        
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.sender, self.user2)
        self.assertEqual(notification.notification_type, 'like')
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_notification_with_content_object(self):
        """Test notification with related object"""
        content_type = ContentType.objects.get_for_model(Post)
        
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='comment',
            message='user2 commented on your post',
            content_type=content_type,
            object_id=self.post.id
        )
        
        self.assertEqual(notification.content_object, self.post)
        self.assertEqual(notification.content_type, content_type)
        self.assertEqual(notification.object_id, self.post.id)

    def test_mark_as_read(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='follow',
            message='user2 started following you'
        )
        
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)
        
        notification.mark_as_read()
        
        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_notification_str(self):
        """Test notification string representation"""
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='mention',
            message='user2 mentioned you'
        )
        
        expected_str = f'mention notification for {self.user1.username}'
        self.assertEqual(str(notification), expected_str)

    def test_notification_ordering(self):
        """Test notification ordering by created_at"""
        # Create notifications with slight delay
        notification1 = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='like',
            message='First notification'
        )
        
        notification2 = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='comment',
            message='Second notification'
        )
        
        notifications = Notification.objects.all()
        self.assertEqual(notifications.first(), notification2)  # Most recent first

    def test_notification_types(self):
        """Test all notification types are valid"""
        valid_types = ['like', 'comment', 'follow', 'mention', 'post', 'system']
        
        for notification_type in valid_types:
            notification = Notification.objects.create(
                recipient=self.user1,
                notification_type=notification_type,
                message=f'Test {notification_type} notification'
            )
            self.assertEqual(notification.notification_type, notification_type)

    def test_system_notification(self):
        """Test system notification without sender"""
        notification = Notification.objects.create(
            recipient=self.user1,
            notification_type='system',
            message='System maintenance scheduled'
        )
        
        self.assertIsNone(notification.sender)
        self.assertEqual(notification.notification_type, 'system')

    def test_notification_indexes(self):
        """Test that database indexes are properly created"""
        # This is more of a structural test
        from django.db import connection
        
        with connection.cursor() as cursor:
            # Check if indexes exist (implementation depends on database)
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='notifications_notification'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            # Should have indexes for recipient/created_at and is_read
            self.assertTrue(any('recipient' in idx for idx in indexes))
            self.assertTrue(any('is_read' in idx for idx in indexes))