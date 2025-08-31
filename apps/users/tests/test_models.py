# File: DjangoVerseHub/apps/users/tests/test_models.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from datetime import date, timedelta

from ..models import CustomUser, Profile

User = get_user_model()


class CustomUserModelTest(TestCase):
    """Test cases for CustomUser model"""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }

    def test_create_user(self):
        """Test creating a user"""
        user = User.objects.create_user(**self.user_data)
        
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])
        self.assertTrue(user.check_password(self.user_data['password']))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.email_verified)

    def test_create_superuser(self):
        """Test creating a superuser"""
        user = User.objects.create_superuser(
            email='admin@example.com',
            username='admin',
            password='adminpass123'
        )
        
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_user_str_method(self):
        """Test user string representation"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(str(user), self.user_data['email'])

    def test_get_full_name(self):
        """Test get_full_name method"""
        user = User.objects.create_user(**self.user_data)
        expected_name = f"{self.user_data['first_name']} {self.user_data['last_name']}"
        self.assertEqual(user.get_full_name(), expected_name)

    def test_get_short_name(self):
        """Test get_short_name method"""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.get_short_name(), self.user_data['first_name'])

    def test_email_unique_constraint(self):
        """Test that email must be unique"""
        User.objects.create_user(**self.user_data)
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email=self.user_data['email'],
                username='different_username',
                password='password123'
            )

    def test_username_unique_constraint(self):
        """Test that username must be unique"""
        User.objects.create_user(**self.user_data)
        
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email='different@example.com',
                username=self.user_data['username'],
                password='password123'
            )

    def test_is_verified_property(self):
        """Test is_verified property"""
        user = User.objects.create_user(**self.user_data)
        self.assertFalse(user.is_verified)
        
        user.email_verified = True
        user.save()
        self.assertTrue(user.is_verified)

    def test_update_login_stats(self):
        """Test update_login_stats method"""
        user = User.objects.create_user(**self.user_data)
        initial_count = user.login_count
        
        user.update_login_stats('192.168.1.1')
        
        self.assertEqual(user.login_count, initial_count + 1)
        self.assertEqual(user.last_login_ip, '192.168.1.1')
        self.assertIsNotNone(user.last_login)


class ProfileModelTest(TestCase):
    """Test cases for Profile model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        # Profile should be created automatically via signals
        
    def test_profile_created_automatically(self):
        """Test that profile is created when user is created"""
        self.assertTrue(hasattr(self.user, 'profile'))
        self.assertIsInstance(self.user.profile, Profile)

    def test_profile_str_method(self):
        """Test profile string representation"""
        expected_str = f"{self.user.username}'s profile"
        self.assertEqual(str(self.user.profile), expected_str)

    def test_display_name_property(self):
        """Test display_name property"""
        profile = self.user.profile
        
        # Should return username when full_name is empty
        self.assertEqual(profile.display_name, self.user.username)
        
        # Should return full_name when available and show_real_name is True
        profile.full_name = 'Test User'
        profile.show_real_name = True
        profile.save()
        self.assertEqual(profile.display_name, 'Test User')
        
        # Should return username when show_real_name is False
        profile.show_real_name = False
        profile.save()
        self.assertEqual(profile.display_name, self.user.username)

    def test_avatar_url_property(self):
        """Test avatar_url property"""
        profile = self.user.profile
        
        # Should return default avatar URL when no avatar
        self.assertEqual(profile.avatar_url, '/static/images/default-avatar.png')

    def test_profile_defaults(self):
        """Test default values for profile"""
        profile = self.user.profile
        
        self.assertTrue(profile.is_public)
        self.assertFalse(profile.show_email)
        self.assertTrue(profile.show_real_name)
        self.assertTrue(profile.email_notifications)
        self.assertTrue(profile.push_notifications)
        self.assertFalse(profile.marketing_emails)
        self.assertEqual(profile.theme, 'light')
        self.assertEqual(profile.timezone, 'UTC')
        self.assertEqual(profile.language, 'en')

    def test_profile_choices(self):
        """Test profile field choices"""
        profile = self.user.profile
        
        # Test gender choices
        valid_genders = ['M', 'F', 'O', 'N']
        for gender in valid_genders:
            profile.gender = gender
            profile.save()
            self.assertEqual(profile.gender, gender)

        # Test theme choices
        valid_themes = ['light', 'dark', 'auto']
        for theme in valid_themes:
            profile.theme = theme
            profile.save()
            self.assertEqual(profile.theme, theme)

    def test_profile_url_fields(self):
        """Test URL field validation"""
        profile = self.user.profile
        
        valid_urls = [
            'https://example.com',
            'http://www.example.com',
            'https://twitter.com/username'
        ]
        
        for url in valid_urls:
            profile.website = url
            profile.twitter = url
            profile.linkedin = url
            profile.github = url
            profile.save()
            
            self.assertEqual(profile.website, url)
            self.assertEqual(profile.twitter, url)
            self.assertEqual(profile.linkedin, url)
            self.assertEqual(profile.github, url)

    def test_profile_text_length_limits(self):
        """Test text field length limits"""
        profile = self.user.profile
        
        # Test bio max length (500 characters)
        long_bio = 'a' * 501
        profile.bio = long_bio
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_profile_managers(self):
        """Test profile managers"""
        # Create additional test users
        User.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='pass123'
        )
        inactive_user = User.objects.create_user(
            email='inactive@example.com',
            username='inactive',
            password='pass123',
            is_active=False
        )
        private_user = User.objects.create_user(
            email='private@example.com',
            username='private',
            password='pass123'
        )
        private_user.profile.is_public = False
        private_user.profile.save()
        
        # Test get_active_profiles
        active_profiles = Profile.objects.get_active_profiles()
        self.assertEqual(active_profiles.count(), 3)  # Excludes inactive user
        
        # Test get_public_profiles
        public_profiles = Profile.objects.get_public_profiles()
        self.assertEqual(public_profiles.count(), 2)  # Excludes private and inactive users

    def test_profile_search(self):
        """Test profile search functionality"""
        # Create user with searchable content
        user2 = User.objects.create_user(
            email='john@example.com',
            username='johndoe',
            password='pass123'
        )
        user2.profile.full_name = 'John Doe'
        user2.profile.bio = 'Django developer from San Francisco'
        user2.profile.save()
        
        # Test search by username
        results = Profile.objects.search_profiles('johndoe')
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first(), user2.profile)
        
        # Test search by full name
        results = Profile.objects.search_profiles('John')
        self.assertEqual(results.count(), 1)
        
        # Test search by bio
        results = Profile.objects.search_profiles('Django')
        self.assertEqual(results.count(), 1)
        
        # Test case insensitive search
        results = Profile.objects.search_profiles('JOHN')
        self.assertEqual(results.count(), 1)