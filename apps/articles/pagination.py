# File: DjangoVerseHub/apps/articles/pagination.py

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.http import Http404


class CachedPaginator(Paginator):
    """Paginator with caching support"""
    
    def __init__(self, object_list, per_page, cache_key=None, cache_timeout=300, **kwargs):
        self.cache_key = cache_key
        self.cache_timeout = cache_timeout
        super().__init__(object_list, per_page, **kwargs)
    
    @property
    def count(self):
        """Cache the count for better performance"""
        if self.cache_key:
            cache_key = f"{self.cache_key}:count"
            count = cache.get(cache_key)
            if count is None:
                count = super().count
                cache.set(cache_key, count, self.cache_timeout)
            return count
        return super().count


class ArticlePaginator:
    """Custom paginator for articles with additional features"""
    
    def __init__(self, queryset, per_page=10, cache_timeout=300):
        self.queryset = queryset
        self.per_page = per_page
        self.cache_timeout = cache_timeout
    
    def paginate(self, page_number, cache_key_prefix=None):
        """Paginate queryset with optional caching"""
        paginator = Paginator(self.queryset, self.per_page)
        
        try:
            page = paginator.page(page_number)
        except PageNotAnInteger:
            page = paginator.page(1)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)
        
        # Cache the page if cache key is provided
        if cache_key_prefix:
            cache_key = f"{cache_key_prefix}:page:{page.number}"
            cached_page = cache.get(cache_key)
            if cached_page is None:
                cache.set(cache_key, page, self.cache_timeout)
        
        return {
            'page': page,
            'paginator': paginator,
            'is_paginated': page.has_other_pages(),
            'page_range': self.get_page_range(page, paginator),
        }
    
    def get_page_range(self, page, paginator, display_pages=7):
        """Get a range of pages to display in pagination"""
        current_page = page.number
        total_pages = paginator.num_pages
        
        if total_pages <= display_pages:
            return range(1, total_pages + 1)
        
        half_display = display_pages // 2
        
        if current_page <= half_display:
            return range(1, display_pages + 1)
        elif current_page > total_pages - half_display:
            return range(total_pages - display_pages + 1, total_pages + 1)
        else:
            return range(current_page - half_display, current_page + half_display + 1)


class SearchPaginator(ArticlePaginator):
    """Paginator specifically for search results"""
    
    def __init__(self, queryset, query, per_page=10, cache_timeout=300):
        super().__init__(queryset, per_page, cache_timeout)
        self.query = query
    
    def paginate(self, page_number, cache_key_prefix=None):
        """Paginate search results with query-specific caching"""
        if cache_key_prefix and self.query:
            cache_key_prefix = f"{cache_key_prefix}:search:{hash(self.query)}"
        
        return super().paginate(page_number, cache_key_prefix)


class CategoryPaginator(ArticlePaginator):
    """Paginator for category-specific articles"""
    
    def __init__(self, queryset, category_slug, per_page=10, cache_timeout=300):
        super().__init__(queryset, per_page, cache_timeout)
        self.category_slug = category_slug
    
    def paginate(self, page_number, cache_key_prefix=None):
        """Paginate category articles with category-specific caching"""
        if cache_key_prefix and self.category_slug:
            cache_key_prefix = f"{cache_key_prefix}:category:{self.category_slug}"
        
        return super().paginate(page_number, cache_key_prefix)


class TagPaginator(ArticlePaginator):
    """Paginator for tag-specific articles"""
    
    def __init__(self, queryset, tag_slug, per_page=10, cache_timeout=300):
        super().__init__(queryset, per_page, cache_timeout)
        self.tag_slug = tag_slug
    
    def paginate(self, page_number, cache_key_prefix=None):
        """Paginate tag articles with tag-specific caching"""
        if cache_key_prefix and self.tag_slug:
            cache_key_prefix = f"{cache_key_prefix}:tag:{self.tag_slug}"
        
        return super().paginate(page_number, cache_key_prefix)


class AuthorPaginator(ArticlePaginator):
    """Paginator for author-specific articles"""
    
    def __init__(self, queryset, author_id, per_page=10, cache_timeout=300):
        super().__init__(queryset, per_page, cache_timeout)
        self.author_id = author_id
    
    def paginate(self, page_number, cache_key_prefix=None):
        """Paginate author articles with author-specific caching"""
        if cache_key_prefix and self.author_id:
            cache_key_prefix = f"{cache_key_prefix}:author:{self.author_id}"
        
        return super().paginate(page_number, cache_key_prefix)


def paginate_queryset(queryset, page, per_page=10, allow_empty_first_page=True):
    """Helper function to paginate any queryset"""
    paginator = Paginator(queryset, per_page, allow_empty_first_page=allow_empty_first_page)
    
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        if page == 1 and allow_empty_first_page:
            page_obj = paginator.page(1)
        else:
            raise Http404("Page not found")
    
    return page_obj, paginator


def get_pagination_context(page_obj, paginator, request):
    """Get pagination context for templates"""
    page_range = get_elided_page_range(paginator, page_obj.number)
    
    return {
        'page_obj': page_obj,
        'paginator': paginator,
        'page_range': page_range,
        'is_paginated': page_obj.has_other_pages(),
        'has_previous': page_obj.has_previous(),
        'has_next': page_obj.has_next(),
        'previous_page_number': page_obj.previous_page_number() if page_obj.has_previous() else None,
        'next_page_number': page_obj.next_page_number() if page_obj.has_next() else None,
    }


def get_elided_page_range(paginator, page_number, on_each_side=3, on_ends=2):
    """Get elided page range for large page sets"""
    try:
        return paginator.get_elided_page_range(
            page_number, 
            on_each_side=on_each_side, 
            on_ends=on_ends
        )
    except AttributeError:
        # Fallback for older Django versions
        return paginator.page_range