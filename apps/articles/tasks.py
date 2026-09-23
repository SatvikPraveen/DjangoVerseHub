# File: DjangoVerseHub/apps/articles/tasks.py

import logging
import os

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from PIL import Image

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_article_images(self, article_id):
    """Process article images (resize, optimize)"""
    from .models import Article

    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        logger.warning('process_article_images: article %s no longer exists', article_id)
        return

    if not article.featured_image:
        return

    try:
        image_path = article.featured_image.path
        if os.path.exists(image_path):
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                max_size = (1200, 800)
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)
                    img.save(image_path, 'JPEG', quality=85, optimize=True)
                    logger.info('Processed featured image for article %s', article_id)
    except Exception as exc:
        logger.error('Failed to process images for article %s: %s', article_id, exc)
        raise self.retry(countdown=60, exc=exc)


@shared_task
def cleanup_unused_media():
    """Clean up unused media files.

    Placeholder: listing/deleting orphaned files depends on the storage backend and is
    intentionally not implemented here.
    """
    from .models import Article

    used_images = set(
        Article.objects.exclude(featured_image='').exclude(featured_image__isnull=True)
        .values_list('featured_image', flat=True)
    )
    logger.info('cleanup_unused_media: %d featured images in use', len(used_images))
    return 0


@shared_task
def update_trending_articles():
    """Warm the trending/popular/featured caches."""
    from .cache import ArticleCacheManager

    try:
        ArticleCacheManager.cache_popular_articles()
        ArticleCacheManager.cache_featured_articles()
        logger.info('Refreshed article caches')
    except Exception as e:
        logger.error('Failed to refresh article caches: %s', e)


@shared_task(bind=True, max_retries=3)
def generate_article_preview(self, article_id):
    """Generate article preview/summary"""
    from .models import Article

    try:
        article = Article.objects.get(id=article_id)
    except Article.DoesNotExist:
        return

    if not article.summary and article.content:
        summary = article.content[:200].strip()
        if len(article.content) > 200:
            summary += '...'
        # update_fields keeps this from creating a revision for a purely derived change
        Article.objects.filter(pk=article.pk).update(summary=summary)
        logger.info('Generated summary for article %s', article_id)


@shared_task
def notify_followers(author_id, article_id):
    """
    Manually fan out a 'new article' notification to an author's followers.

    Normal publishing already triggers this through apps.notifications.signals;
    this task exists for re-sends from the admin or shell and goes through the
    same notify() helper so it is deduplicated and preference-aware.
    """
    from django.contrib.auth import get_user_model

    from apps.notifications.signals import notify

    from .models import Article

    User = get_user_model()
    try:
        author = User.objects.get(id=author_id)
        article = Article.objects.get(id=article_id)
    except (User.DoesNotExist, Article.DoesNotExist):
        return 0

    if not article.is_published:
        return 0

    notifications = notify(
        author.followers.filter(is_active=True),
        author,
        'post',
        f'{author.get_full_name() or author.username} published a new article: "{article.title}"',
        target=article,
    )
    logger.info('Notified %d followers about article %s', len(notifications), article_id)
    return len(notifications)
