# File: DjangoVerseHub/apps/users/tests/test_api.py

import json
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token

User = get_user_model()


class UserAPITest(TestCase):
    """Test cases for User API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.token = Token.objects.create(user=self.user)

    def test_user_registration_api(self):
        """Test user registration via API"""
        url = reverse('users:user-register')
        data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'complexpass123',
            'password_confirm': 'complexpass123'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('token', response.data)
        
        # Check user was created
        user_exists = User.objects.filter(email='newuser@example.com').exists()
        self.assertTrue(user_exists)

    def test_user_registration_duplicate_email(self):
        """Test registration with duplicate email"""
        url = reverse('users:user-register')
        data = {
            'email': 'test@example.com',  # Already exists
            'username': 'newuser',
            'password': 'complexpass123',
            'password_confirm': 'complexpass123'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_user_login_api(self):
        """Test user login via API"""
        url = reverse('users:user-login')
        data = {
            'username': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('token', response.data)

    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        url = reverse('users:user-login')
        data = {
            'username': 'test@example.com',
            'password': 'wrongpass'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_logout_api(self):
        """Test user logout via API"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:user-logout')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Token should be deleted
        token_exists = Token.objects.filter(user=self.user).exists()
        self.assertFalse(token_exists)

    def test_get_current_user_profile(self):
        """Test getting current user's profile"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:user-me')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertEqual(response.data['username'], self.user.username)

    def test_change_password_api(self):
        """Test changing password via API"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:user-change-password')
        data = {
            'current_password': 'testpass123',
            'new_password': 'newpass123',
            'new_password_confirm': 'newpass123'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))

    def test_change_password_wrong_current(self):
        """Test changing password with wrong current password"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:user-change-password')
        data = {
            'current_password': 'wrongpass',
            'new_password': 'newpass123',
            'new_password_confirm': 'newpass123'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_list_api(self):
        """Test user list API"""
        # Create additional users
        User.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='pass123'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:user-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

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
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:user-list')
        response = self.client.get(url)
        
        # Should only see public profiles
        usernames = [user['username'] for user in response.data['results']]
        self.assertIn('testuser', usernames)
        self.assertNotIn('private', usernames)

    def test_unauthorized_access(self):
        """Test unauthorized access to protected endpoints"""
        url = reverse('users:user-me')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileAPITest(TestCase):
    """Test cases for Profile API endpoints"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.token = Token.objects.create(user=self.user)

    def test_get_own_profile(self):
        """Test getting own profile"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:profile-detail', kwargs={'pk': 'me'})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user.username)

    def test_update_own_profile(self):
        """Test updating own profile"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:profile-detail', kwargs={'pk': self.user.profile.pk})
        data = {
            'full_name': 'Updated Name',
            'bio': 'Updated bio',
            'location': 'New Location',
            'theme': 'dark'
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check profile was updated
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.full_name, 'Updated Name')
        self.assertEqual(self.user.profile.bio, 'Updated bio')

    def test_cannot_update_others_profile(self):
        """Test that users cannot update other users' profiles"""
        # Create another user
        other_user = User.objects.create_user(
            email='other@example.com',
            username='other',
            password='pass123'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:profile-detail', kwargs={'pk': other_user.profile.pk})
        data = {'full_name': 'Hacked Name'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_profile_search_api(self):
        """Test profile search API"""
        # Create searchable profile
        user2 = User.objects.create_user(
            email='john@example.com',
            username='johndoe',
            password='pass123'
        )
        user2.profile.full_name = 'John Doe'
        user2.profile.bio = 'Django developer'
        user2.profile.save()
        
        url = reverse('users:profile-search')
        response = self.client.get(url, {'q': 'john'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['username'], 'johndoe')

    def test_profile_search_empty_query(self):
        """Test profile search with empty query"""
        url = reverse('users:profile-search')
        response = self.client.get(url, {'q': ''})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)

    def test_profile_stats_api(self):
        """Test profile stats API"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:profile-stats', kwargs={'pk': self.user.profile.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('activity_stats', response.data)
        self.assertIn('profile_completion', response.data)

    def test_profile_stats_private_profile(self):
        """Test accessing stats of private profile"""
        # Create private profile user
        private_user = User.objects.create_user(
            email='private@example.com',
            username='private',
            password='pass123'
        )
        private_user.profile.is_public = False
        private_user.profile.save()
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:profile-stats', kwargs={'pk': private_user.profile.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_public_profile_access(self):
        """Test accessing public profiles without authentication"""
        url = reverse('users:profile-detail', kwargs={'pk': self.user.profile.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user.username)

    def test_private_profile_access_unauthenticated(self):
        """Test accessing private profile without authentication"""
        self.user.profile.is_public = False
        self.user.profile.save()
        
        url = reverse('users:profile-detail', kwargs={'pk': self.user.profile.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_profile_list_api(self):
        """Test profile list API"""
        # Create additional profiles
        User.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='pass123'
        )
        
        url = reverse('users:profile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_profile_image_upload_api(self):
        """Test profile image upload via API"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        from io import BytesIO
        
        # Create test image
        image = Image.new('RGB', (100, 100), color='red')
        img_io = BytesIO()
        image.save(img_io, format='JPEG')
        img_io.seek(0)
        
        avatar = SimpleUploadedFile('avatar.jpg', img_io.getvalue(), content_type='image/jpeg')
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('users:profile-detail', kwargs={'pk': self.user.profile.pk})
        data = {'avatar': avatar}
        response = self.client.patch(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)