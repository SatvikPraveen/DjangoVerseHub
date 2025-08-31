# File: DjangoVerseHub/apps/articles/search.py

from django.db.models import Q, F, Value
from django.db.models.functions import Concat
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, SearchHeadline
)
from django.core.cache import cache
import re
from .models import Article, Category, Tag


class ArticleSearchManager:
    """Manager for article search functionality"""
    
    @staticmethod
    def normalize_query(query_string):
        """Normalize search query by removing extra spaces and special chars"""
        query_string = re.sub(r'[^\w\s]', ' ', query_string)
        return ' '.join(query_string.split())
    
    @staticmethod
    def get_search_cache_key(query, filters=None):
        """Generate cache key for search results"""
        cache_key = f"search:articles:{hash(query)}"
        if filters:
            filter_hash = hash(str(sorted(filters.items())))
            cache_key += f":{filter_hash}"
        return cache_key
    
    @classmethod
    def basic_search(cls, query, filters=None):
        """Basic search using icontains"""
        if not query:
            return Article.objects.none()
        
        normalized_query = cls.normalize_query(query)
        search_fields = Q(title__icontains=normalized_query) | \
                       Q(content__icontains=normalized_query) | \
                       Q(summary__icontains=normalized_query)
        
        queryset = Article.published.filter(search_fields)
        
        # Apply additional filters
        if filters:
            queryset = cls.apply_filters(queryset, filters)
        
        return queryset.select_related('author', 'category').prefetch_related('tags')
    
    @classmethod
    def postgresql_search(cls, query, filters=None, use_cache=True):
        """Advanced search using PostgreSQL full-text search"""
        if not query:
            return Article.objects.none()
        
        # Check cache first
        if use_cache:
            cache_key = cls.get_search_cache_key(query, filters)
            cached_results = cache.get(cache_key)
            if cached_results is not None:
                return cached_results
        
        normalized_query = cls.normalize_query(query)
        search_query = SearchQuery(normalized_query)
        search_vector = SearchVector('title', weight='A') + \
                       SearchVector('summary', weight='B') + \
                       SearchVector('content', weight='C')
        
        queryset = Article.published.annotate(
            search=search_vector,
            rank=SearchRank(search_vector, search_query)
        ).filter(
            search=search_query
        ).order_by('-rank', '-created_at')
        
        # Apply additional filters
        if filters:
            queryset = cls.apply_filters(queryset, filters)
        
        queryset = queryset.select_related('author', 'category').prefetch_related('tags')
        
        # Cache results for 15 minutes
        if use_cache:
            cache.set(cache_key, queryset, 900)
        
        return queryset
    
    @classmethod
    def apply_filters(cls, queryset, filters):
        """Apply additional filters to search queryset"""
        if filters.get('category'):
            queryset = queryset.filter(category__slug=filters['category'])
        
        if filters.get('tag'):
            queryset = queryset.filter(tags__slug=filters['tag'])
        
        if filters.get('author'):
            queryset = queryset.filter(author__email__icontains=filters['author'])
        
        if filters.get('date_from'):
            queryset = queryset.filter(published_at__gte=filters['date_from'])
        
        if filters.get('date_to'):
            queryset = queryset.filter(published_at__lte=filters['date_to'])
        
        if filters.get('featured_only'):
            queryset = queryset.filter(is_featured=True)
        
        return queryset
    
    @classmethod
    def search_with_highlights(cls, query, filters=None):
        """Search with highlighted results"""
        try:
            # Try PostgreSQL full-text search with highlights
            normalized_query = cls.normalize_query(query)
            search_query = SearchQuery(normalized_query)
            search_vector = SearchVector('title', weight='A') + \
                           SearchVector('summary', weight='B') + \
                           SearchVector('content', weight='C')
            
            queryset = Article.published.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query),
                headline_title=SearchHeadline('title', search_query),
                headline_summary=SearchHeadline('summary', search_query),
                headline_content=SearchHeadline('content', search_query, max_words=50)
            ).filter(
                search=search_query
            ).order_by('-rank', '-created_at')
            
        except Exception:
            # Fallback to basic search
            queryset = cls.basic_search(query, filters)
        
        # Apply filters
        if filters:
            queryset = cls.apply_filters(queryset, filters)
        
        return queryset.select_related('author', 'category').prefetch_related('tags')
    
    @classmethod
    def get_search_suggestions(cls, query, limit=5):
        """Get search suggestions based on query"""
        if len(query) < 2:
            return []
        
        # Search in titles for suggestions
        suggestions = Article.published.filter(
            title__icontains=query
        ).values_list('title', flat=True)[:limit]
        
        return list(suggestions)
    
    @classmethod
    def search_autocomplete(cls, query, limit=10):
        """Autocomplete for search queries"""
        if len(query) < 2:
            return {'articles': [], 'categories': [], 'tags': []}
        
        # Article suggestions
        articles = Article.published.filter(
            Q(title__icontains=query) | Q(summary__icontains=query)
        ).values('id', 'title', 'slug')[:limit//2]
        
        # Category suggestions
        categories = Category.objects.filter(
            name__icontains=query
        ).values('id', 'name', 'slug')[:limit//4]
        
        # Tag suggestions
        tags = Tag.objects.filter(
            name__icontains=query
        ).values('id', 'name', 'slug')[:limit//4]
        
        return {
            'articles': list(articles),
            'categories': list(categories),
            'tags': list(tags),
        }


class CategorySearchManager:
    """Manager for category search"""
    
    @classmethod
    def search_categories(cls, query):
        """Search categories by name and description"""
        if not query:
            return Category.objects.none()
        
        return Category.objects.active().filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )


class TagSearchManager:
    """Manager for tag search"""
    
    @classmethod
    def search_tags(cls, query):
        """Search tags by name"""
        if not query:
            return Tag.objects.none()
        
        return Tag.objects.filter(name__icontains=query)
    
    @classmethod
    def popular_tags_for_search(cls, limit=20):
        """Get popular tags for search filters"""
        cache_key = f'popular_tags_search:{limit}'
        tags = cache.get(cache_key)
        
        if tags is None:
            tags = Tag.objects.popular(limit)
            cache.set(cache_key, tags, 3600)  # Cache for 1 hour
        
        return tags


def search_all(query, filters=None, use_postgresql=True):
    """Main search function that combines all search functionality"""
    if use_postgresql:
        try:
            return ArticleSearchManager.postgresql_search(query, filters)
        except Exception:
            # Fallback to basic search
            return ArticleSearchManager.basic_search(query, filters)
    else:
        return ArticleSearchManager.basic_search(query, filters)


def get_trending_searches(limit=10):
    """Get trending search queries (would need to implement search logging)"""
    # This would require implementing search query logging
    # For now, return empty list
    return []