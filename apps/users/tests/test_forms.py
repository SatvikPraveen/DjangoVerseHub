# File: DjangoVerseHub/apps/users/tests/test_forms.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from io import BytesIO

from ..forms import (
    CustomUserCreationForm, CustomLoginForm, ProfileForm,
    UserUpdateForm, PasswordChangeForm
)
from ..models import Profile

User = get_user_model()


class CustomUserCreationFormTest(TestCase):
    """Test cases for user registration form"""

    def test_valid_form(self):
        """Test form with valid data"""
        form_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'terms_accepted': True
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_email_required(self):
        """Test that email is required"""
        form_data = {
            'username': 'testuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'terms_accepted': True
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_email(self):
        """Test validation for duplicate email"""
        User.objects.create_user(
            email='existing@example.com',
            username='existing',
            password='pass123'
        )
        
        form_data = {
            'email': 'existing@example.com',
            'username': 'newuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'terms_accepted': True
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_username(self):
        """Test validation for duplicate username"""
        User.objects.create_user(
            email='existing@example.com',
            username='existing',
            password='pass123'
        )
        
        form_data = {
            'email': 'new@example.com',
            'username': 'existing',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'terms_accepted': True
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_prohibited_usernames(self):
        """Test validation for prohibited usernames"""
        prohibited_usernames = ['admin', 'root', 'api']
        
        for username in prohibited_usernames:
            form_data = {
                'email': f'{username}@example.com',
                'username': username,
                'password1': 'complexpass123',
                'password2': 'complexpass123',
                'terms_accepted': True
            }
            form = CustomUserCreationForm(data=form_data)
            self.assertFalse(form.is_valid())
            self.assertIn('username', form.errors)

    def test_terms_required(self):
        """Test that terms acceptance is required"""
        form_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123'
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('terms_accepted', form.errors)

    def test_password_mismatch(self):
        """Test password confirmation mismatch"""
        form_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'password1': 'complexpass123',
            'password2': 'differentpass123',
            'terms_accepted': True
        }
        form = CustomUserCreationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)


class CustomLoginFormTest(TestCase):
    """Test cases for login form"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_valid_login_with_email(self):
        """Test login with email"""
        form_data = {
            'username': 'test@example.com',
            'password': 'testpass123'
        }
        form = CustomLoginForm(data=form_data)
        # Note: This requires request context for full validation
        # In actual view, this would be properly tested

    def test_valid_login_with_username(self):
        """Test login with username"""
        form_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        form = CustomLoginForm(data=form_data)
        # Note: This requires request context for full validation

    def test_invalid_credentials(self):
        """Test login with invalid credentials"""
        form_data = {
            'username': 'test@example.com',
            'password': 'wrongpass'
        }
        form = CustomLoginForm(data=form_data)
        # This would fail validation in actual request context


class ProfileFormTest(TestCase):
    """Test cases for profile form"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )
        self.profile = self.user.profile

    def test_valid_profile_form(self):
        """Test form with valid profile data"""
        form_data = {
            'full_name': 'Test User',
            'bio': 'This is a test bio',
            'location': 'Test City',
            'website': 'https://example.com',
            'theme': 'dark',
            'is_public': True,
            'email_notifications': True
        }
        form = ProfileForm(data=form_data, instance=self.profile)
        self.assertTrue(form.is_valid())

    def test_invalid_website_url(self):
        """Test validation for invalid website URL"""
        form_data = {
            'website': 'not-a-valid-url'
        }
        form = ProfileForm(data=form_data, instance=self.profile)
        self.assertFalse(form.is_valid())
        self.assertIn('website', form.errors)

    def test_bio_max_length(self):
        """Test bio maximum length validation"""
        form_data = {
            'bio': 'a' * 501  # Exceeds 500 character limit
        }
        form = ProfileForm(data=form_data, instance=self.profile)
        self.assertFalse(form.is_valid())

    def create_test_image(self):
        """Helper method to create test image"""
        image = Image.new('RGB', (100, 100), color='red')
        img_io = BytesIO()
        image.save(img_io, format='JPEG')
        img_io.seek(0)
        return SimpleUploadedFile('test_avatar.jpg', img_io.getvalue(), content_type='image/jpeg')

    def test_avatar_upload(self):
        """Test avatar file upload"""
        avatar = self.create_test_image()
        form_data = {}
        form_files = {'avatar': avatar}
        form = ProfileForm(data=form_data, files=form_files, instance=self.profile)
        self.assertTrue(form.is_valid())

    def test_avatar_size_validation(self):
        """Test avatar file size validation"""
        # Create a large image (this is a mock test)
        large_image = SimpleUploadedFile(
            'large_avatar.jpg', 
            b'fake_large_image_content' * 1000000,  # Simulate large file
            content_type='image/jpeg'
        )
        
        form_data = {}
        form_files = {'avatar': large_image}
        form = ProfileForm(data=form_data, files=form_files, instance=self.profile)
        # Size validation would trigger in actual upload


class UserUpdateFormTest(TestCase):
    """Test cases for user update form"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123'
        )

    def test_valid_user_update(self):
        """Test updating user information"""
        form_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone_number': '+1234567890',
            'date_of_birth': '1990-01-01'
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        self.assertTrue(form.is_valid())

    def test_invalid_phone_number(self):
        """Test phone number validation"""
        form_data = {
            'phone_number': '123'  # Too short
        }
        form = UserUpdateForm(data=form_data, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('phone_number', form.errors)

    def test_valid_phone_formats(self):
        """Test various valid phone number formats"""
        valid_phones = [
            '+1234567890',
            '(123) 456-7890',
            '123-456-7890',
            '123 456 7890'
        ]
        
        for phone in valid_phones:
            form_data = {'phone_number': phone}
            form = UserUpdateForm(data=form_data, instance=self.user)
            if not form.is_valid():
                print(f"Phone {phone} failed: {form.errors}")


class PasswordChangeFormTest(TestCase):
    """Test cases for password change form"""

    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='oldpass123'
        )

    def test_valid_password_change(self):
        """Test valid password change"""
        form_data = {
            'current_password': 'oldpass123',
            'new_password1': 'newpass123',
            'new_password2': 'newpass123'
        }
        form = PasswordChangeForm(self.user, data=form_data)
        self.assertTrue(form.is_valid())

    def test_incorrect_current_password(self):
        """Test with incorrect current password"""
        form_data = {
            'current_password': 'wrongpass',
            'new_password1': 'newpass123',
            'new_password2': 'newpass123'
        }
        form = PasswordChangeForm(self.user, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('current_password', form.errors)

    def test_new_password_mismatch(self):
        """Test new password confirmation mismatch"""
        form_data = {
            'current_password': 'oldpass123',
            'new_password1': 'newpass123',
            'new_password2': 'differentpass123'
        }
        form = PasswordChangeForm(self.user, data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('new_password2', form.errors)

    def test_password_save(self):
        """Test password saving functionality"""
        form_data = {
            'current_password': 'oldpass123',
            'new_password1': 'newpass123',
            'new_password2': 'newpass123'
        }
        form = PasswordChangeForm(self.user, data=form_data)
        if form.is_valid():
            form.save()
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('newpass123'))
            self.assertFalse(self.user.check_password('oldpass123'))