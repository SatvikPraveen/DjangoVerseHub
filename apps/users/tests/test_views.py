# File: DjangoVerseHub/apps/users/tests/test_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


class UserViewsTest(TestCase):
    """Test cases for user views"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_signup_view_get(self):
        """Test signup view GET request"""
        response = self.client.get(reverse('users:signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create your account')
        self.assertContains(response, 'form')

    def test_signup_view_post_valid(self):
        """Test signup view with valid data"""
        data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'terms_accepted': True
        }
        response = self.client.post(reverse('users:signup'), data)
        
        # Should redirect to profile after successful signup
        self.assertEqual(response.status_code, 302)
        
        # Check user was created
        user_exists = User.objects.filter(email='newuser@example.com').exists()
        self.assertTrue(user_exists)
        
        # Check user is logged in
        new_user = User.objects.get(email='newuser@example.com')
        self.assertEqual(int(self.client.session['_auth_user_id']), new_user.id)

    def test_signup_view_post_invalid(self):
        """Test signup view with invalid data"""
        data = {
            'email': 'invalid-email',
            'username': '',
            'password1': '123',
            'password2': 'different',
        }
        response = self.client.post(reverse('users:signup'), data)
        
        # Should stay on signup page with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error')

    def test_login_view_get(self):
        """Test login view GET request"""
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome back')
        self.assertContains(response, 'form')

    def test_login_view_post_valid(self):
        """Test login view with valid credentials"""
        data = {
            'username': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(reverse('users:login'), data)
        
        # Should redirect after successful login
        self.assertEqual(response.status_code, 302)
        
        # Check user is logged in
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.id)

    def test_login_view_post_invalid(self):
        """Test login view with invalid credentials"""
        data = {
            'username': 'test@example.com',
            'password': 'wrongpass'
        }
        response = self.client.post(reverse('users:login'), data)
        
        # Should stay on login page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error')

    def test_login_redirect_authenticated_user(self):
        """Test that authenticated users are redirected from login page"""
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('users:login'))
        self.assertEqual(response.status_code, 302)

    def test_logout_view(self):
        """Test logout functionality"""
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('users:logout'))
        
        # Should redirect
        self.assertEqual(response.status_code, 302)
        
        # Check user is logged out
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_profile_detail_view(self):
        """Test profile detail view"""
        response = self.client.get(
            reverse('users:profile', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.username)
        self.assertContains(response, self.user.profile.display_name)

    def test_profile_detail_private_profile(self):
        """Test viewing private profile"""
        # Make profile private
        self.user.profile.is_public = False
        self.user.profile.save()
        
        # Create another user
        other_user = User.objects.create_user(
            email='other@example.com',
            username='other',
            password='pass123'
        )
        
        # Try to view private profile as other user
        self.client.login(username='other@example.com', password='pass123')
        response = self.client.get(
            reverse('users:profile', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_profile_update_view_get(self):
        """Test profile update view GET request"""
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('users:profile_edit'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')

    def test_profile_update_view_post(self):
        """Test profile update view POST request"""
        self.client.login(username='test@example.com', password='testpass123')
        data = {
            'full_name': 'Updated Name',
            'bio': 'Updated bio',
            'location': 'New Location',
            'theme': 'dark',
            'is_public': True,
            'email_notifications': True,
            'push_notifications': False,
            'marketing_emails': False
        }
        response = self.client.post(reverse('users:profile_edit'), data)
        
        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)
        
        # Check profile was updated
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Updated Name')
        self.assertEqual(self.user.profile.bio, 'Updated bio')
        self.assertEqual(self.user.profile.theme, 'dark')

    def test_profile_update_requires_login(self):
        """Test that profile update requires authentication"""
        response = self.client.get(reverse('users:profile_edit'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_profile_settings_view_get(self):
        """Test profile settings view GET request"""
        self.client.login(username='test@example.com', password='testpass123')
        response = self.client.get(reverse('users:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profile Settings')
        self.assertContains(response, 'Change Password')

    def test_profile_settings_update_profile(self):
        """Test updating profile via settings"""
        self.client.login(username='test@example.com', password='testpass123')
        data = {
            'update_profile': '',
            'first_name': 'Updated',
            'last_name': 'Name',
            'full_name': 'Updated Full Name',
            'bio': 'Updated bio',
            'theme': 'dark',
            'is_public': True,
            'email_notifications': True,
            'push_notifications': True,
            'marketing_emails': False
        }
        response = self.client.post(reverse('users:settings'), data)
        
        # Should redirect after successful update
        self.assertEqual(response.status_code, 302)
        
        # Check updates
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')

    def test_profile_settings_change_password(self):
        """Test changing password via settings"""
        self.client.login(username='test@example.com', password='testpass123')
        data = {
            'change_password': '',
            'current_password': 'testpass123',
            'new_password1': 'newpass123',
            'new_password2': 'newpass123'
        }
        response = self.client.post(reverse('users:settings'), data)
        
        # Should redirect after successful change
        self.assertEqual(response.status_code, 302)
        
        # Check password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))

    def test_user_list_view(self):
        """Test user list view"""
        # Create additional users
        User.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='pass123'
        )
        User.objects.create_user(
            email='user3@example.com',
            username='user3',
            password='pass123'
        )
        
        response = self.client.get(reverse('users:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'testuser')
        self.assertContains(response, 'user2')
        self.assertContains(response, 'user3')

    def test_user_list_search(self):
        """Test user list search functionality"""
        # Create user with searchable content
        User.objects.create_user(
            email='john@example.com',
            username='johndoe',
            password='pass123'
        )
        
        response = self.client.get(reverse('users:list'), {'q': 'john'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'johndoe')
        self.assertNotContains(response, 'testuser')

    def test_user_list_excludes_private_profiles(self):
        """Test that user list excludes private profiles"""
        # Create user with private profile
        private_user = User.objects.create_user(
            email='private@example.com',
            username='private',
            password='pass123'
        )
        private_user.profile.is_public = False
        private_user.profile.save()
        
        response = self.client.get(reverse('users:list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'private')
        self.assertContains(response, 'testuser')

    def test_user_list_pagination(self):
        """Test user list pagination"""
        # Create many users to test pagination
        for i in range(25):
            User.objects.create_user(
                email=f'user{i}@example.com',
                username=f'user{i}',
                password='pass123'
            )
        
        response = self.client.get(reverse('users:list'))
        self.assertEqual(response.status_code, 200)
        
        # Check pagination context
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['users']), 20)  # Default page size