"""
File: tests/test_integration.py
Cross-app integration tests.
Tests the interaction between different Django applications and their components.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.test.client import Client
from django.urls import reverse
from django.core import mail
from django.conf import settings
from django.db import transaction
from unittest.mock import patch, Mock

from accounts.models import UserProfile
from notifications.models import Notification
from core.tasks import send_welcome_email


class UserAccountIntegrationTestCase(TestCase):
    """Test integration between user accounts and other apps."""
    
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'complex_password_123',
            'password2': 'complex_password_123',
            'first_name': 'Test',
            'last_name': 'User'
        }
    
    def test_user_registration_creates_profile(self):
        """Test that user registration automatically creates a profile."""
        response = self.client.post(reverse('accounts:register'), self.user_data)
        
        # Should redirect after successful registration
        self.assertEqual(response.status_code, 302)
        
        # User should be created
        user = User.objects.get(username='testuser')
        self.assertTrue(user.is_active)
        
        # Profile should be automatically created
        self.assertTrue(hasattr(user, 'userprofile'))
        profile = user.userprofile
        self.assertEqual(profile.user, user)
    
    def test_user_registration_sends_welcome_notification(self):
        """Test that user registration creates a welcome notification."""
        self.client.post(reverse('accounts:register'), self.user_data)
        user = User.objects.get(username='testuser')
        
        # Welcome notification should be created
        notifications = Notification.objects.filter(
            recipient=user,
            notification_type='welcome'
        )
        self.assertTrue(notifications.exists())
        
        notification = notifications.first()
        self.assertIn('Welcome', notification.title)
        self.assertFalse(notification.is_read)
    
    @patch('core.tasks.send_welcome_email.delay')
    def test_user_registration_triggers_welcome_email(self, mock_email_task):
        """Test that user registration triggers welcome email task."""
        self.client.post(reverse('accounts:register'), self.user_data)
        user = User.objects.get(username='testuser')
        
        # Welcome email task should be called
        mock_email_task.assert_called_once_with(user.id)
    
    def test_user_login_updates_last_login(self):
        """Test that user login updates last_login timestamp."""
        # Create user
        user = User.objects.create_user(**{
            k: v for k, v in self.user_data.items() 
            if k not in ['password1', 'password2']
        })
        user.set_password('complex_password_123')
        user.save()
        
        initial_last_login = user.last_login
        
        # Login
        login_data = {
            'username': 'testuser',
            'password': 'complex_password_123'
        }
        response = self.client.post(reverse('accounts:login'), login_data)
        
        # Should redirect after successful login
        self.assertEqual(response.status_code, 302)
        
        # Last login should be updated
        user.refresh_from_db()
        self.assertNotEqual(user.last_login, initial_last_login)


class NotificationIntegrationTestCase(TestCase):
    """Test notification system integration with other apps."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
    
    def test_notification_creation_and_display(self):
        """Test notification creation and display in views."""
        # Create notification
        notification = Notification.objects.create(
            recipient=self.user,
            title='Test Notification',
            message='This is a test notification',
            notification_type='info'
        )
        
        # Login user
        self.client.login(username='testuser', password='testpass123')
        
        # Check notification appears in list
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Notification')
        self.assertContains(response, 'This is a test notification')
        
        # Notification should be unread
        self.assertContains(response, 'unread')
    
    def test_notification_marking_as_read(self):
        """Test marking notifications as read."""
        notification = Notification.objects.create(
            recipient=self.user,
            title='Test Notification',
            message='This is a test notification',
            notification_type='info'
        )
        
        self.client.login(username='testuser', password='testpass123')
        
        # Mark as read
        response = self.client.post(
            reverse('notifications:mark-read', kwargs={'pk': notification.pk})
        )
        self.assertEqual(response.status_code, 302)
        
        # Notification should be marked as read
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)


class APIIntegrationTestCase(TestCase):
    """Test API integration with frontend and other systems."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
    
    def test_api_authentication_integration(self):
        """Test API authentication works with session authentication."""
        # Login via web interface
        self.client.login(username='testuser', password='testpass123')
        
        # Access API endpoint
        response = self.client.get(reverse('api:user-detail', kwargs={'pk': self.user.pk}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['username'], 'testuser')
    
    def test_api_user_profile_integration(self):
        """Test API returns user profile data correctly."""
        # Create profile data
        profile = self.user.userprofile
        profile.bio = 'Test bio'
        profile.save()
        
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.get(reverse('api:user-detail', kwargs={'pk': self.user.pk}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['profile']['bio'], 'Test bio')


class EmailIntegrationTestCase(TestCase):
    """Test email integration across applications."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_welcome_email_integration(self):
        """Test welcome email is sent after user registration."""
        # Clear any existing emails
        mail.outbox = []
        
        # Trigger welcome email
        send_welcome_email(self.user.id)
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Welcome', email.subject)
        self.assertEqual(email.to, [self.user.email])
        self.assertIn(self.user.username, email.body)
    
    def test_notification_email_integration(self):
        """Test notification emails are sent for important notifications."""
        # Create high priority notification
        notification = Notification.objects.create(
            recipient=self.user,
            title='Important Notification',
            message='This is important',
            notification_type='urgent',
            email_sent=False
        )
        
        # Clear existing emails
        mail.outbox = []
        
        # Trigger email notification
        from notifications.tasks import send_notification_email
        send_notification_email(notification.id)
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('Important Notification', email.subject)
        self.assertEqual(email.to, [self.user.email])
        
        # Check notification is marked as email sent
        notification.refresh_from_db()
        self.assertTrue(notification.email_sent)


class DatabaseIntegrationTestCase(TransactionTestCase):
    """Test database transactions and integrity across apps."""
    
    def test_user_deletion_cascades_correctly(self):
        """Test that deleting a user properly cascades to related objects."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create related objects
        profile = user.userprofile
        profile.bio = 'Test bio'
        profile.save()
        
        notification = Notification.objects.create(
            recipient=user,
            title='Test Notification',
            message='Test message',
            notification_type='info'
        )
        
        # Verify objects exist
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertTrue(Notification.objects.filter(recipient=user).exists())
        
        # Delete user
        user.delete()
        
        # Verify cascading deletion
        self.assertFalse(UserProfile.objects.filter(id=profile.id).exists())
        self.assertFalse(Notification.objects.filter(id=notification.id).exists())
    
    def test_atomic_transactions_work_correctly(self):
        """Test that database transactions work correctly across apps."""
        with self.assertRaises(Exception):
            with transaction.atomic():
                user = User.objects.create_user(
                    username='testuser',
                    email='test@example.com',
                    password='testpass123'
                )
                
                # Create notification
                Notification.objects.create(
                    recipient=user,
                    title='Test Notification',
                    message='Test message',
                    notification_type='info'
                )
                
                # Force an exception to test rollback
                raise Exception("Test exception")
        
        # Verify nothing was created due to rollback
        self.assertFalse(User.objects.filter(username='testuser').exists())
        self.assertFalse(Notification.objects.filter(title='Test Notification').exists())


class CacheIntegrationTestCase(TestCase):
    """Test caching integration across applications."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
    
    @patch('django.core.cache.cache.get')
    @patch('django.core.cache.cache.set')
    def test_user_profile_caching(self, mock_cache_set, mock_cache_get):
        """Test that user profiles are properly cached."""
        mock_cache_get.return_value = None
        
        self.client.login(username='testuser', password='testpass123')
        
        # Access user profile view
        response = self.client.get(
            reverse('accounts:profile', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify cache was checked and set
        mock_cache_get.assert_called()
        mock_cache_set.assert_called()