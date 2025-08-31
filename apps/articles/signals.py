# File: DjangoVerseHub/apps/articles/signals.py

from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from django.core.cache import cache
from .models import Article, Category, Tag
from .cache import ArticleCacheManager
from .tasks import process_article_images, notify_followers


@receiver(post_save, sender=Article)
def article_post_save(sender, instance, created, **kwargs):
    """Handle article post-save operations"""
    # Clear cache
    ArticleCacheManager.invalidate_article_cache(instance.id)
    ArticleCacheManager.invalidate_article_list_cache()
    
    if created:
        # Process images in background
        if instance.featured_image:
            process_article_images.delay(instance.id)
        
        # Send notifications to followers (if implemented)
        # notify_followers.delay(instance.author.id, instance.id)
    
    # Update search index (if using search engine like Elasticsearch)
    # update_search_index.delay('article', instance.id)


@receiver(post_delete, sender=Article)
def article_post_delete(sender, instance, **kwargs):
    """Handle article deletion"""
    # Clear cache
    ArticleCacheManager.invalidate_article_cache(instance.id)
    ArticleCacheManager.invalidate_article_list_cache()
    
    # Clean up files
    if instance.featured_image:
        instance.featured_image.delete(save=False)
    
    # Remove from search index
    # remove_from_search_index.delay('article', instance.id)


@receiver(m2m_changed, sender=Article.tags.through)
def article_tags_changed(sender, instance, action, pk_set, **kwargs):
    """Handle article tags changes"""
    if action in ['post_add', 'post_remove', 'post_clear']:
        # Clear cache
        ArticleCacheManager.invalidate_article_cache(instance.id)
        ArticleCacheManager.invalidate_article_list_cache()


@receiver(post_save, sender=Category)
def category_post_save(sender, instance, created, **kwargs):
    """Handle category post-save operations"""
    # Clear category cache
    cache_keys = [
        'categories:active',
        f'popular_categories:10',
    ]
    cache.delete_many(cache_keys)


@receiver(post_save, sender=Tag)
def tag_post_save(sender, instance, created, **kwargs):
    """Handle tag post-save operations"""
    # Clear tag cache
    cache_keys = [
        f'popular_tags:20',
        f'popular_tags_search:20',
    ]
    cache.delete_many(cache_keys)