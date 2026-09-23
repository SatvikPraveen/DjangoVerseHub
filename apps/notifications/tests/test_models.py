# File: DjangoVerseHub/apps/notifications/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.urls import reverse
from apps.notifications.models import Notification, NotificationPreference
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

class NotificationManagerTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(email='m1@test.com', password='x', username='m1')
        self.user2 = User.objects.create_user(email='m2@test.com', password='x', username='m2')
        self.user3 = User.objects.create_user(email='m3@test.com', password='x', username='m3')
        self.article = Article.objects.create(title='Target', author=self.user1, content='c', status='draft')

    def test_unread_and_read_querysets(self):
        n1 = Notification.objects.create(recipient=self.user1, notification_type='system', message='a')
        n2 = Notification.objects.create(recipient=self.user1, notification_type='system', message='b')
        Notification.objects.create(recipient=self.user2, notification_type='system', message='c')
        n2.mark_as_read()

        self.assertEqual(list(Notification.objects.unread(self.user1)), [n1])
        self.assertEqual(Notification.objects.unread().count(), 2)
        self.assertEqual(list(Notification.objects.for_user(self.user1).read()), [n2])
        self.assertEqual(Notification.objects.of_type('system').count(), 3)

    def test_mark_all_read(self):
        Notification.objects.create(recipient=self.user1, notification_type='like', message='a')
        Notification.objects.create(recipient=self.user1, notification_type='like', message='b')
        other = Notification.objects.create(recipient=self.user2, notification_type='like', message='c')

        self.assertEqual(Notification.objects.mark_all_read(self.user1), 2)
        self.assertEqual(Notification.objects.unread(self.user1).count(), 0)
        self.assertTrue(all(n.read_at for n in Notification.objects.for_user(self.user1)))
        other.refresh_from_db()
        self.assertFalse(other.is_read)
        self.assertEqual(Notification.objects.mark_all_read(self.user1), 0)

    def test_notify_bulk_creates_and_skips_sender(self):
        created = Notification.objects.notify(
            [self.user1, self.user2, self.user3, self.user1], self.user1, 'post', 'New post', target=self.article,
        )
        self.assertEqual(len(created), 2)
        self.assertTrue(all(n.pk for n in created))
        self.assertEqual({n.recipient for n in created}, {self.user2, self.user3})
        self.assertEqual(created[0].content_object, self.article)
        self.assertEqual(created[0].object_id, str(self.article.pk))

    def test_notify_accepts_single_user_and_queryset(self):
        self.assertEqual(len(Notification.objects.notify(self.user2, self.user1, 'system', 'hi')), 1)
        qs = User.objects.filter(pk__in=[self.user2.pk, self.user3.pk])
        self.assertEqual(len(Notification.objects.notify(qs, None, 'system', 'hello everyone')), 2)

    def test_notify_dedupes_unread_only(self):
        Notification.objects.notify([self.user2], self.user1, 'like', 'liked', target=self.article)
        self.assertEqual(Notification.objects.notify([self.user2], self.user1, 'like', 'liked', target=self.article), [])
        Notification.objects.mark_all_read(self.user2)
        self.assertEqual(len(Notification.objects.notify([self.user2], self.user1, 'like', 'liked', target=self.article)), 1)
        self.assertEqual(
            len(Notification.objects.notify([self.user2], self.user1, 'like', 'again', target=self.article, dedupe=False)), 1
        )

    def test_notify_respects_in_app_preference(self):
        NotificationPreference.objects.create(user=self.user2, in_app_like=False)
        self.assertEqual(Notification.objects.notify([self.user2, self.user3], self.user1, 'like', 'liked'), [self.user3.notifications.get()])
        # system notifications cannot be disabled
        self.assertEqual(len(Notification.objects.notify([self.user2], None, 'system', 'maintenance')), 1)

    def test_notify_empty_recipients(self):
        self.assertEqual(Notification.objects.notify([], self.user1, 'like', 'x'), [])
        self.assertEqual(Notification.objects.notify(None, self.user1, 'like', 'x'), [])
        self.assertEqual(Notification.objects.notify([self.user1], self.user1, 'like', 'x'), [])


class NotificationPresentationTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='p@test.com', password='x', username='p')
        self.article = Article.objects.create(title='Target', author=self.user, content='c', status='published')

    def test_url_icon_color_and_read_alias(self):
        n = Notification.objects.create(
            recipient=self.user, notification_type='comment', message='m',
            content_type=ContentType.objects.get_for_model(Article), object_id=str(self.article.pk),
        )
        self.assertEqual(n.url, self.article.get_absolute_url())
        self.assertEqual(n.icon, 'chat-fill')
        self.assertEqual(n.color, 'primary')
        self.assertFalse(n.read)
        n.mark_as_read()
        self.assertTrue(n.read)
        n.mark_as_unread()
        self.assertFalse(n.is_read)
        self.assertIsNone(n.read_at)

    def test_url_falls_back_when_target_missing(self):
        n = Notification.objects.create(recipient=self.user, notification_type='system', message='m')
        self.assertEqual(n.url, reverse('notifications:list'))
        n2 = Notification.objects.create(
            recipient=self.user, notification_type='post', message='m',
            content_type=ContentType.objects.get_for_model(Article), object_id=str(self.article.pk),
        )
        self.article.delete()
        n2 = Notification.objects.get(pk=n2.pk)
        self.assertIsNone(n2.target)
        self.assertEqual(n2.url, reverse('notifications:list'))


class NotificationPreferenceModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='pref@test.com', password='x', username='pref')

    def test_for_user_creates_defaults(self):
        prefs = NotificationPreference.for_user(self.user)
        self.assertTrue(prefs.in_app_comment)
        self.assertEqual(prefs.digest_frequency, 'daily')
        self.assertEqual(NotificationPreference.for_user(self.user).pk, prefs.pk)
        self.assertEqual(str(prefs), 'Notification preferences for pref')

    def test_allows_in_app_and_email(self):
        prefs = NotificationPreference.objects.create(user=self.user, in_app_like=False, email_like=True, email_post=False)
        self.assertFalse(prefs.allows_in_app('like'))
        self.assertTrue(prefs.allows_in_app('comment'))
        self.assertTrue(prefs.allows_in_app('system'))
        self.assertTrue(prefs.allows_email('like'))
        self.assertFalse(prefs.allows_email('post'))
        self.assertTrue(prefs.allows_email('system'))
        self.assertIn('like', prefs.email_types())
        self.assertNotIn('post', prefs.email_types())

    def test_profile_email_switch_is_master(self):
        prefs = NotificationPreference.objects.create(user=self.user, email_comment=True)
        self.user.profile.email_notifications = False
        self.user.profile.save()
        self.assertFalse(prefs.allows_email('comment'))
        self.assertFalse(prefs.allows_email('system'))
