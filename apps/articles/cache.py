# File: DjangoVerseHub/apps/articles/cache.py

from django.core.cache import cache
from django.conf import settings
from django.db.models import Count, Q
from .models import Article, Category, Tag


class ArticleCacheManager:
    """Cache manager for article-related data"""
    
    @staticmethod
    def get_article_cache_key(article_id):
        return f'article:{article_id}'
    
    @staticmethod
    def get_article_list_cache_key(page=1, category=None, tag=None, search=None):
        key_parts = ['articles', f'page:{page}']
        if category:
            key_parts.append(f'category:{category}')
        if tag:
            key_parts.append(f'tag:{tag}')
        if search:
            key_parts.append(f'search:{search}')
        return ':'.join(key_parts)
    
    @staticmethod
    def get_popular_articles_cache_key(days=7, limit=10):
        return f'popular_articles:{days}:{limit}'
    
    @staticmethod
    def get_trending_articles_cache_key(days=7, limit=10):
        return f'trending_articles:{days}:{limit}'
    
    @staticmethod
    def get_featured_articles_cache_key(limit=5):
        return f'featured_articles:{limit}'
    
    @staticmethod
    def get_related_articles_cache_key(article_id, limit=5):
        return f'related_articles:{article_id}:{limit}'
    
    @classmethod
    def cache_article(cls, article, timeout=3600):
        """Cache individual article"""
        cache_key = cls.get_article_cache_key(article.id)
        article_data = {
            'id': str(article.id),
            'title': article.title,
            'slug': article.slug,
            'content': article.content,
            'summary': article.summary,
            'author_name': article.author.get_full_name(),
            'category_name': article.category.name if article.category else None,
            'tags': list(article.tags.values_list('name', flat=True)),
            'featured_image_url': article.get_featured_image_url(),
            'views_count': article.views_count,
            'likes_count': article.likes_count,
            'reading_time': article.reading_time,
            'created_at': article.created_at.isoformat(),
            'published_at': article.published_at.isoformat() if article.published_at else None,
        }
        cache.set(cache_key, article_data, timeout)
        return article_data
    
    @classmethod
    def get_cached_article(cls, article_id):
        """Get cached article data"""
        cache_key = cls.get_article_cache_key(article_id)
        return cache.get(cache_key)
    
    @classmethod
    def cache_popular_articles(cls, days=7, limit=10, timeout=1800):
        """Cache popular articles"""
        cache_key = cls.get_popular_articles_cache_key(days, limit)
        articles = Article.published.popular().select_related('author', 'category')[:limit]
        articles_data = []
        
        for article in articles:
            articles_data.append({
                'id': str(article.id),
                'title': article.title,
                'slug': article.slug,
                'author_name': article.author.get_full_name(),
                'category_name': article.category.name if article.category else None,
                'featured_image_url': article.get_featured_image_url(),
                'views_count': article.views_count,
                'likes_count': article.likes_count,
                'created_at': article.created_at.isoformat(),
            })
        
        cache.set(cache_key, articles_data, timeout)
        return articles_data
    
    @classmethod
    def get_cached_popular_articles(cls, days=7, limit=10):
        """Get cached popular articles"""
        cache_key = cls.get_popular_articles_cache_key(days, limit)
        articles = cache.get(cache_key)
        if articles is None:
            articles = cls.cache_popular_articles(days, limit)
        return articles
    
    @classmethod
    def cache_featured_articles(cls, limit=5, timeout=3600):
        """Cache featured articles"""
        cache_key = cls.get_featured_articles_cache_key(limit)
        articles = Article.published.featured().select_related('author', 'category')[:limit]
        articles_data = []
        
        for article in articles:
            articles_data.append({
                'id': str(article.id),
                'title': article.title,
                'slug': article.slug,
                'summary': article.summary,
                'author_name': article.author.get_full_name(),
                'category_name': article.category.name if article.category else None,
                'featured_image_url': article.get_featured_image_url(),
                'created_at': article.created_at.isoformat(),
            })
        
        cache.set(cache_key, articles_data, timeout)
        return articles_data
    
    @classmethod
    def get_cached_featured_articles(cls, limit=5):
        """Get cached featured articles"""
        cache_key = cls.get_featured_articles_cache_key(limit)
        articles = cache.get(cache_key)
        if articles is None:
            articles = cls.cache_featured_articles(limit)
        return articles
    
    @classmethod
    def invalidate_article_cache(cls, article_id):
        """Invalidate all cache related to an article"""
        cache_keys = [
            cls.get_article_cache_key(article_id),
            cls.get_related_articles_cache_key(article_id, 5),
            cls.get_popular_articles_cache_key(),
            cls.get_trending_articles_cache_key(),
            cls.get_featured_articles_cache_key(),
        ]
        cache.delete_many(cache_keys)
    
    @classmethod
    def invalidate_article_list_cache(cls):
        """Invalidate article list cache"""
        # This would require a more sophisticated cache key pattern
        # For now, just invalidate common keys
        cache_keys = [
            'articles:page:1',
            cls.get_popular_articles_cache_key(),
            cls.get_trending_articles_cache_key(),
            cls.get_featured_articles_cache_key(),
        ]
        cache.delete_many(cache_keys)


class CategoryCacheManager:
    """Cache manager for category-related data"""
    
    @staticmethod
    def get_categories_cache_key():
        return 'categories:active'
    
    @staticmethod
    def get_popular_categories_cache_key(limit=10):
        return f'popular_categories:{limit}'
    
    @classmethod
    def cache_active_categories(cls, timeout=3600):
        """Cache active categories"""
        cache_key = cls.get_categories_cache_key()
        categories = Category.objects.active().order_by('name')
        categories_data = [{
            'id': category.id,
            'name': category.name,
            'slug': category.slug,
            'description': category.description,
            'article_count': category.article_count,
        } for category in categories]
        
        cache.set(cache_key, categories_data, timeout)
        return categories_data
    
    @classmethod
    def get_cached_active_categories(cls):
        """Get cached active categories"""
        cache_key = cls.get_categories_cache_key()
        categories = cache.get(cache_key)
        if categories is None:
            categories = cls.cache_active_categories()
        return categories


class TagCacheManager:
    """Cache manager for tag-related data"""
    
    @staticmethod
    def get_popular_tags_cache_key(limit=20):
        return f'popular_tags:{limit}'
    
    @classmethod
    def cache_popular_tags(cls, limit=20, timeout=3600):
        """Cache popular tags"""
        cache_key = cls.get_popular_tags_cache_key(limit)
        tags = Tag.objects.popular(limit)
        tags_data = [{
            'id': tag.id,
            'name': tag.name,
            'slug': tag.slug,
            'article_count': tag.article_count,
        } for tag in tags]
        
        cache.set(cache_key, tags_data, timeout)
        return tags_data
    
    @classmethod
    def get_cached_popular_tags(cls, limit=20):
        """Get cached popular tags"""
        cache_key = cls.get_popular_tags_cache_key(limit)
        tags = cache.get(cache_key)
        if tags is None:
            tags = cls.cache_popular_tags(limit)
        return tags