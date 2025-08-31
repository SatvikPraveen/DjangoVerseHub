# File: DjangoVerseHub/apps/notifications/tests/test_signals.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from apps.notifications.models import Notification
from apps.posts.models import Post, Like
from apps.comments.models import Comment
from apps.accounts.models import Follow

User = get_user_model()


class NotificationSignalsTest(TestCase):
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

    @patch('apps.notifications.signals.send_notification_to_user')
    def test_like_notification_created(self, mock_send_notification):
        """Test that like creates notification"""
        initial_count = Notification.objects.count()
        
        # Create like
        like = Like.objects.create(user=self.user2, post=self.post)
        
        # Check notification was created
        self.assertEqual(Notification.objects.count(), initial_count + 1)
        
        notification = Notification.objects.latest('created_at')
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.sender, self.user2)
        self.assertEqual(notification.notification_type, 'like')
        self.assertIn('liked your post', notification.message)
        
        # Check send_notification_to_user was called
        mock_send_notification.assert_called_once_with(notification)

    @patch('apps.notifications.signals.send_notification_to_user')
    def test_like_own_post_no_notification(self, mock_send_notification):
        """Test that liking own post doesn't create notification"""
        initial_count = Notification.objects.count()
        
        # User likes their own post
        like = Like.objects.create(user=self.user1, post=self.post)
        
        # No notification should be created
        self.assertEqual(Notification.objects.count(), initial_count)
        mock_send_notification.assert_not_called()

    @patch('apps.notifications.signals.send_notification_to_user')
    def test_comment_notification_created(self, mock_send_notification):
        """Test that comment creates notification"""
        initial_count = Notification.objects.count()
        
        # Create comment
        comment = Comment.objects.create(
            author=self.user2,
            post=self.post,
            content='Great post!'
        )
        
        # Check notification was created
        self.assertEqual(Notification.objects.count(), initial_count + 1)
        
        notification = Notification.objects.latest('created_at')
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.sender, self.user2)
        self.assertEqual(notification.notification_type, 'comment')
        self.assertIn('commented on your post', notification.message)
        
        mock_send_notification.assert_called_once_with(notification)

    @patch('apps.notifications.signals.send_notification_to_user')
    def test_comment_own_post_no_notification(self, mock_send_notification):
        """Test that commenting on own post doesn't create notification"""
        initial_count = Notification.objects.count()
        
        # User comments on their own post
        comment = Comment.objects.create(
            author=self.user1,
            post=self.post,
            content='My own comment'
        )
        
        # No notification should be created
        self.assertEqual(Notification.objects.count(), initial_count)
        mock_send_notification.assert_not_called()

    @patch('apps.notifications.signals.send_notification_to_user')
    def test_follow_notification_created(self, mock_send_notification):
        """Test that follow creates notification"""
        initial_count = Notification.objects.count()
        
        # Create follow
        follow = Follow.objects.create(
            follower=self.user2,
            following=self.user1
        )
        
        # Check notification was created
        self.assertEqual(Notification.objects.count(), initial_count + 1)
        
        notification = Notification.objects.latest('created_at')
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.sender, self.user2)
        self.assertEqual(notification.notification_type, 'follow')
        self.assertIn('started following you', notification.message)
        
        mock_send_notification.assert_called_once_with(notification)

    @patch('apps.notifications.signals.send_notification_to_user')
    def test_new_post_notification_to_followers(self, mock_send_notification):
        """Test that new post creates notifications for followers"""
        # User2 follows User1
        Follow.objects.create(follower=self.user2, following=self.user1)
        
        # Create third user who also follows User1
        user3 = User.objects.create_user(
            username='user3',
            email='user3@test.com',
            password='testpass123'
        )
        Follow.objects.create(follower=user3, following=self.user1)
        
        initial_count = Notification.objects.count()
        
        # User1 creates new post
        new_post = Post.objects.create(
            author=self.user1,
            content='New post for followers'
        )
        
        # Should create notifications for both followers
        self.assertEqual(Notification.objects.count(), initial_count + 2)
        
        # Check both followers got notifications
        notifications = Notification.objects.filter(
            notification_type='post',
            sender=self.user1
        ).order_by('recipient__username')
        
        self.assertEqual(len(notifications), 2)
        self.assertEqual(notifications[0].recipient, self.user2)
        self.assertEqual(notifications[1].recipient, user3)
        
        # Check send_notification_to_user was called for each notification
        self.assertEqual(mock_send_notification.call_count, 2)

    @patch('channels.layers.get_channel_layer')
    def test_send_notification_to_user_websocket(self, mock_get_channel_layer):
        """Test send_notification_to_user sends WebSocket message"""
        from apps.notifications.signals import send_notification_to_user
        
        # Mock channel layer
        mock_channel_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer
        
        # Create notification
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='like',
            message='Test notification'
        )
        
        # Call the function
        send_notification_to_user(notification)
        
        # Check channel layer was used
        self.assertEqual(mock_channel_layer.group_send.call_count, 2)  # notification + unread count
        
        # Verify group name
        group_name = f'notifications_{self.user1.id}'
        calls = mock_channel_layer.group_send.call_args_list
        
        # First call should be notification message
        self.assertEqual(calls[0][0][0], group_name)
        self.assertEqual(calls[0][0][1]['type'], 'notification_message')
        
        # Second call should be unread count
        self.assertEqual(calls[1][0][0], group_name)
        self.assertEqual(calls[1][0][1]['type'], 'unread_count_update')

    @patch('channels.layers.get_channel_layer')
    def test_send_notification_no_channel_layer(self, mock_get_channel_layer):
        """Test send_notification_to_user handles missing channel layer"""
        from apps.notifications.signals import send_notification_to_user
        
        # Mock no channel layer
        mock_get_channel_layer.return_value = None
        
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='like',
            message='Test notification'
        )
        
        # Should not raise exception
        try:
            send_notification_to_user(notification)
        except Exception as e:
            self.fail(f"send_notification_to_user raised {e} unexpectedly")