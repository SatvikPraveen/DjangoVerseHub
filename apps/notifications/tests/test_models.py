# File: DjangoVerseHub/apps/notifications/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from apps.notifications.models import Notification
from apps.articles.models import Article, Category

User = get_user_model()


class NotificationModelTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email='user1@test.com', password='testpass123', username='user1'
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com', password='testpass123', username='user2'
        )
        self.category = Category.objects.create(
            name='Test Category', slug='test-category'
        )
        self.article = Article.objects.create(
            title='Test Article',
            slug='test-article',
            author=self.user1,
            category=self.category,
            content='Test content',
            status='published',
        )

    def test_notification_creation(self):
        """Test basic notification creation."""
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='like',
            message='user2 liked your article',
        )
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.sender, self.user2)
        self.assertEqual(notification.notification_type, 'like')
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

    def test_notification_with_content_object(self):
        """Test notification with a related GenericForeignKey object."""
        content_type = ContentType.objects.get_for_model(Article)
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='comment',
            message='user2 commented on your article',
            content_type=content_type,
            object_id=str(self.article.pk),
        )
        self.assertEqual(notification.content_object, self.article)
        self.assertEqual(notification.content_type, content_type)
        self.assertEqual(notification.object_id, str(self.article.pk))

    def test_mark_as_read(self):
        """Test mark_as_read() sets is_read=True and records read_at."""
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='follow',
            message='user2 started following you',
        )
        self.assertFalse(notification.is_read)
        self.assertIsNone(notification.read_at)

        notification.mark_as_read()

        self.assertTrue(notification.is_read)
        self.assertIsNotNone(notification.read_at)

    def test_mark_as_read_is_idempotent(self):
        """Calling mark_as_read twice should not change the read_at timestamp."""
        notification = Notification.objects.create(
            recipient=self.user1,
            notification_type='system',
            message='System message',
        )
        notification.mark_as_read()
        first_read_at = notification.read_at
        notification.mark_as_read()
        self.assertEqual(notification.read_at, first_read_at)

    def test_notification_str(self):
        """Test __str__ representation."""
        notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type='mention',
            message='user2 mentioned you',
        )
        expected = f'mention notification for {self.user1.username}'
        self.assertEqual(str(notification), expected)

    def test_notification_ordering(self):
        """Most-recently created notification should appear first."""
        n1 = Notification.objects.create(
            recipient=self.user1,
            notification_type='like',
            message='First',
        )
        n2 = Notification.objects.create(
            recipient=self.user1,
            notification_type='comment',
            message='Second',
        )
        qs = Notification.objects.all()
        self.assertEqual(qs.first(), n2)

    def test_valid_notification_types(self):
        """All declared NOTIFICATION_TYPES should be storable."""
        valid_types = [choice[0] for choice in Notification.NOTIFICATION_TYPES]
        for ntype in valid_types:
            n = Notification.objects.create(
                recipient=self.user1,
                notification_type=ntype,
                message=f'Test {ntype}',
            )
            self.assertEqual(n.notification_type, ntype)