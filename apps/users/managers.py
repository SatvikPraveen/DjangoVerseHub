# File: DjangoVerseHub/apps/users/managers.py

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """Custom user manager for email-based authentication"""
    
    def create_user(self, email, password, **extra_fields):
        """Create and save a user with the given email and password"""
        if not email:
            raise ValueError(_('The Email must be set'))
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a superuser with the given email and password"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class ProfileManager(models.Manager):
    """Manager for Profile model"""
    
    def get_active_profiles(self):
        """Return profiles of active users"""
        return self.filter(user__is_active=True)
    
    def get_verified_profiles(self):
        """Return profiles of verified users"""
        return self.filter(user__email_verified=True)
    
    def get_public_profiles(self):
        """Return public profiles"""
        return self.filter(is_public=True, user__is_active=True)
    
    def search_profiles(self, query):
        """Search profiles by username, full name, or bio"""
        return self.filter(
            models.Q(user__username__icontains=query) |
            models.Q(full_name__icontains=query) |
            models.Q(bio__icontains=query)
        )