# File: DjangoVerseHub/apps/articles/signals.py

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from .cache import ArticleCacheManager
from .models import Article, Category, Tag
from .tasks import notify_followers, process_article_images


def _invalidate_article(instance):
    ArticleCacheManager.invalidate_article_cache(instance.id)
    ArticleCacheManager.invalidate_article_list_cache()


@receiver(post_save, sender=Article)
def article_post_save(sender, instance, created, **kwargs):
    """Handle article post-save operations"""
    _invalidate_article(instance)

    if created and instance.featured_image:
        transaction.on_commit(lambda: process_article_images.delay(str(instance.id)))

    # Notify the author's followers the first time an article goes live
    if getattr(instance, '_just_published', False):
        instance._just_published = False
        transaction.on_commit(lambda: notify_followers.delay(str(instance.author_id), str(instance.id)))


@receiver(post_delete, sender=Article)
def article_post_delete(sender, instance, **kwargs):
    """Handle article deletion"""
    _invalidate_article(instance)

    if instance.featured_image:
        instance.featured_image.delete(save=False)


@receiver(m2m_changed, sender=Article.tags.through)
def article_tags_changed(sender, instance, action, pk_set, **kwargs):
    """Handle article tags changes"""
    if action in ('post_add', 'post_remove', 'post_clear'):
        _invalidate_article(instance)
        cache.delete_many(['popular_tags:20', 'popular_tags_search:20'])


# NOTE: the 'somebody liked your article' notification is created by
# apps.notifications.signals (wired lazily to ArticleLike in its AppConfig.ready).


@receiver(post_save, sender=Category)
def category_post_save(sender, instance, created, **kwargs):
    """Handle category post-save operations"""
    cache.delete_many(['categories:active', 'popular_categories:10'])


@receiver(post_save, sender=Tag)
def tag_post_save(sender, instance, created, **kwargs):
    """Handle tag post-save operations"""
    cache.delete_many(['popular_tags:20', 'popular_tags_search:20'])
