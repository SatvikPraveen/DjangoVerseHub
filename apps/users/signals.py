# File: DjangoVerseHub/apps/users/signals.py

import os
from django.db.models.signals import post_save, post_delete, pre_delete
from django.dispatch import receiver
from django.core.cache import cache
from django.conf import settings

from .models import CustomUser, Profile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a profile when a new user is created"""
    if created:
        Profile.objects.get_or_create(user=instance)
        
        # Send welcome email (if celery task exists)
        try:
            from .tasks import send_welcome_email
            send_welcome_email.delay(instance.id)
        except ImportError:
            pass


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """Save the profile when the user is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_save, sender=Profile)
def clear_user_cache(sender, instance, **kwargs):
    """Clear user-related cache when profile is updated"""
    cache_keys = [
        f'user_profile:{instance.user.id}',
        f'user_data:{instance.user.id}',
        f'public_profile:{instance.user.id}',
        f'user_stats:{instance.user.id}',
    ]
    cache.delete_many(cache_keys)


@receiver(pre_delete, sender=Profile)
def cleanup_profile_files(sender, instance, **kwargs):
    """Clean up profile files when profile is deleted"""
    if instance.avatar and os.path.isfile(instance.avatar.path):
        try:
            os.remove(instance.avatar.path)
        except OSError:
            pass
    
    if instance.cover_image and os.path.isfile(instance.cover_image.path):
        try:
            os.remove(instance.cover_image.path)
        except OSError:
            pass


@receiver(post_delete, sender=CustomUser)
def cleanup_user_cache(sender, instance, **kwargs):
    """Clean up cache when user is deleted"""
    cache_keys = [
        f'user_profile:{instance.id}',
        f'user_data:{instance.id}',
        f'public_profile:{instance.id}',
        f'user_stats:{instance.id}',
    ]
    cache.delete_many(cache_keys)


@receiver(post_save, sender=CustomUser)
def update_user_search_index(sender, instance, created, **kwargs):
    """Update search index when user is created or updated"""
    # This would integrate with search backend like Elasticsearch
    # For now, we'll just update cache
    if hasattr(instance, 'profile'):
        cache.delete(f'user_search:{instance.username}')
        cache.delete(f'user_search:{instance.email}')