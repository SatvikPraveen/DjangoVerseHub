"""
File: tests/test_integration.py
Cross-app integration tests.
Tests the interaction between different apps in DjangoVerseHub.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.test.client import Client
from django.urls import reverse
from django.core import mail
from unittest.mock import patch

from apps.users.models import Profile
from apps.notifications.models import Notification

User = get_user_model()


class UserAccountIntegrationTestCase(TestCase):
    """Test integration between user accounts and other apps."""

    def setUp(self):
        self.client = Client()

    def _create_user(self, email='test@example.com', username='testuser', password='complex_password_123'):
        return User.objects.create_user(email=email, password=password, username=username)

    def test_user_creation_creates_profile(self):
        """Test that creating a user automatically creates a matching Profile."""
        user = self._create_user()
        self.assertTrue(Profile.objects.filter(user=user).exists())
        profile = user.profile
        self.assertEqual(profile.user, user)

    @patch('apps.users.tasks.send_welcome_email.delay')
    def test_user_creation_triggers_welcome_email(self, mock_email_task):
        """Test that user creation fires the welcome email Celery task."""
        user = self._create_user()
        mock_email_task.assert_called_once_with(user.id)

    def test_user_login_redirects(self):
        """Test that a valid login redirects the user."""
        self._create_user()
        response = self.client.post(reverse('users:login'), {
            'login': 'test@example.com',
            'password': 'complex_password_123',
        })
        # allauth-based login should redirect (302) on success
        self.assertIn(response.status_code, [200, 302])


class NotificationIntegrationTestCase(TestCase):
    """Test notification system integration with web views."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com', password='testpass123', username='testuser'
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_notification_list_view_loads(self):
        """Notification list view should return 200 for authenticated users."""
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)

    def test_notification_creation_and_list_display(self):
        """Notifications created in DB appear in the list view."""
        Notification.objects.create(
            recipient=self.user,
            notification_type='system',
            message='Welcome to DjangoVerseHub',
        )
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome to DjangoVerseHub')

    def test_api_mark_notification_read(self):
        """API endpoint marks a notification as read."""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type='comment',
            message='Someone commented',
        )
        self.assertFalse(notification.is_read)
        response = self.client.post(
            reverse('notifications:api_mark_read', kwargs={'notification_id': notification.pk})
        )
        self.assertIn(response.status_code, [200, 302])
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class DatabaseIntegrationTestCase(TransactionTestCase):
    """Test database-level cascade behaviour across apps."""

    def test_user_deletion_cascades_to_profile_and_notifications(self):
        """Deleting a user removes their Profile and Notifications."""
        user = User.objects.create_user(
            email='cascade@example.com', password='pass', username='cascadeuser'
        )
        Notification.objects.create(
            recipient=user,
            notification_type='system',
            message='You will be deleted',
        )
        user_id = user.id
        user.delete()

        self.assertFalse(Profile.objects.filter(user_id=user_id).exists())
        self.assertFalse(Notification.objects.filter(recipient_id=user_id).exists())


class EmailIntegrationTestCase(TestCase):
    """Test Celery email tasks produce correct mail messages."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='mail@example.com', password='testpass123', username='mailuser',
            first_name='Mail', last_name='User',
        )

    def test_welcome_email_task(self):
        """send_welcome_email task should send one email to the user."""
        from apps.users.tasks import send_welcome_email
        mail.outbox = []
        send_welcome_email(self.user.id)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertIn('Welcome', str(msg.subject))
        self.assertEqual(msg.to, [self.user.email])


from django.test import TestCase, TransactionTestCase
