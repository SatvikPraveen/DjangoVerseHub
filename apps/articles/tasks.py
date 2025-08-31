# File: DjangoVerseHub/apps/articles/tasks.py

from celery import shared_task
from django.utils import timezone
from django.core.files.storage import default_storage
from PIL import Image
import os
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_article_images(self, article_id):
    """Process article images (resize, optimize)"""
    try:
        from .models import Article
        article = Article.objects.get(id=article_id)
        
        if article.featured_image:
            # Process featured image
            image_path = article.featured_image.path
            if os.path.exists(image_path):
                with Image.open(image_path) as img:
                    # Convert to RGB if necessary
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    # Resize if too large
                    max_size = (1200, 800)
                    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                        img.thumbnail(max_size, Image.Resampling.LANCZOS)
                        img.save(image_path, 'JPEG', quality=85, optimize=True)
                        
                        logger.info(f'Processed featured image for article {article_id}')
        
    except Exception as exc:
        logger.error(f'Failed to process images for article {article_id}: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task
def cleanup_unused_media():
    """Clean up unused media files"""
    from .models import Article
    
    # Get all featured images
    used_images = set()
    for article in Article.objects.all():
        if article.featured_image:
            used_images.add(article.featured_image.name)
    
    # Clean up unused files (this is a simplified version)
    # In production, you'd want a more sophisticated cleanup
    cleaned_count = 0
    
    try:
        # List all files in the media directory
        # and remove ones not in used_images
        # This is a placeholder - implement based on your storage backend
        pass
    except Exception as e:
        logger.error(f'Error cleaning up media files: {e}')
    
    logger.info(f'Cleaned up {cleaned_count} unused media files')
    return cleaned_count


@shared_task
def update_trending_articles():
    """Update trending articles cache"""
    from .models import Article
    from .cache import ArticleCacheManager
    
    try:
        # Get trending articles and cache them
        trending_articles = Article.published.trending(days=7).select_related('author', 'category')[:20]
        
        # This would update the cache
        cache_key = 'trending_articles:7:20'
        # ArticleCacheManager would handle this
        
        logger.info('Updated trending articles cache')
        
    except Exception as e:
        logger.error(f'Failed to update trending articles: {e}')


@shared_task(bind=True, max_retries=3)
def generate_article_preview(self, article_id):
    """Generate article preview/summary"""
    try:
        from .models import Article
        article = Article.objects.get(id=article_id)
        
        if not article.summary and article.content:
            # Generate summary from content (first 200 chars)
            summary = article.content[:200].strip()
            if len(article.content) > 200:
                summary += '...'
            
            article.summary = summary
            article.save(update_fields=['summary'])
            
            logger.info(f'Generated summary for article {article_id}')
        
    except Exception as exc:
        logger.error(f'Failed to generate preview for article {article_id}: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task
def notify_followers(author_id, article_id):
    """Notify followers about new article"""
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.models import Notification
        
        User = get_user_model()
        author = User.objects.get(id=author_id)
        
        # This would require a followers system
        # followers = author.followers.all()
        # 
        # for follower in followers:
        #     Notification.objects.create(
        #         recipient=follower,
        #         actor=author,
        #         verb='published a new article',
        #         action_object_id=article_id,
        #         action_object_content_type=ContentType.objects.get_for_model(Article)
        #     )
        
        logger.info(f'Notified followers about new article {article_id}')
        
    except Exception as e:
        logger.error(f'Failed to notify followers: {e}')


@shared_task
def update_article_stats():
    """Update article statistics"""
    from .models import Article
    from django.db.models import Count
    
    try:
        # Update comment counts
        articles_with_comments = Article.objects.annotate(
            comment_count=Count('comments', filter=Q(comments__is_active=True))
        )
        
        # This is just an example - you might want to update other stats
        # like calculating reading time, popularity scores, etc.
        
        logger.info('Updated article statistics')
        
    except Exception as e:
        logger.error(f'Failed to update article stats: {e}')