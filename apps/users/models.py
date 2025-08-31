# File: DjangoVerseHub/apps/users/models.py

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.validators import URLValidator
from django.utils import timezone
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile

from .managers import CustomUserManager, ProfileManager


class CustomUser(AbstractUser):
    """Custom User model with email as username field"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)
    
    # Additional fields
    email_verified = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = CustomUserManager()

    class Meta:
        db_table = 'users_customuser'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['-date_joined']

    def __str__(self):
        return self.email

    def get_absolute_url(self):
        return reverse('users:profile', kwargs={'pk': self.pk})
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between"""
        full_name = f'{self.first_name} {self.last_name}'
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user"""
        return self.first_name or self.username
    
    @property
    def is_verified(self):
        """Check if user has verified email"""
        return self.email_verified
    
    def update_login_stats(self, ip_address=None):
        """Update login statistics"""
        self.login_count += 1
        self.last_login_ip = ip_address
        self.last_login = timezone.now()
        self.save(update_fields=['login_count', 'last_login_ip', 'last_login'])


class Profile(models.Model):
    """User profile model with additional information"""
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
        ('N', 'Prefer not to say'),
    ]
    
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ]
    
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='covers/', null=True, blank=True)
    
    # Personal information
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True)
    location = models.CharField(max_length=100, blank=True)
    website = models.URLField(blank=True, validators=[URLValidator()])
    
    # Social links
    twitter = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    github = models.URLField(blank=True)
    
    # Preferences
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Privacy settings
    is_public = models.BooleanField(default=True)
    show_email = models.BooleanField(default=False)
    show_real_name = models.BooleanField(default=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    marketing_emails = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = ProfileManager()

    class Meta:
        db_table = 'users_profile'
        verbose_name = _('Profile')
        verbose_name_plural = _('Profiles')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_absolute_url(self):
        return reverse('users:profile', kwargs={'pk': self.user.pk})
    
    @property
    def display_name(self):
        """Get the display name for the user"""
        if self.full_name and self.show_real_name:
            return self.full_name
        return self.user.username
    
    @property
    def avatar_url(self):
        """Get avatar URL or default"""
        if self.avatar and hasattr(self.avatar, 'url'):
            return self.avatar.url
        return '/static/images/default-avatar.png'
    
    def save(self, *args, **kwargs):
        """Override save to process images"""
        super().save(*args, **kwargs)
        
        # Resize avatar if it exists
        if self.avatar:
            self._resize_image(self.avatar, (300, 300))
        
        # Resize cover image if it exists
        if self.cover_image:
            self._resize_image(self.cover_image, (1200, 400))
    
    def _resize_image(self, image_field, size):
        """Resize image to specified dimensions"""
        try:
            img = Image.open(image_field.path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save the resized image
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            output.seek(0)
            
            # Replace the original image
            image_field.save(
                image_field.name,
                ContentFile(output.getvalue()),
                save=False
            )
        except Exception:
            # If image processing fails, keep the original
            pass