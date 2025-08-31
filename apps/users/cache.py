# File: DjangoVerseHub/apps/users/cache.py

from django.core.cache import cache
from django.conf import settings
from functools import wraps
import hashlib
import json

from .models import CustomUser, Profile


# Cache timeout constants (in seconds)
USER_CACHE_TIMEOUT = 60 * 15  # 15 minutes
PROFILE_CACHE_TIMEOUT = 60 * 30  # 30 minutes
SEARCH_CACHE_TIMEOUT = 60 * 5  # 5 minutes


def cache_user_data(timeout=USER_CACHE_TIMEOUT):
    """Decorator to cache user-related data"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key based on function name and arguments
            key_data = {
                'func': func.__name__,
                'args': str(args),
                'kwargs': str(sorted(kwargs.items()))
            }
            cache_key = f"user_data:{hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()}"
            
            # Try to get from cache first
            result = cache.get(cache_key)
            if result is not None:
                return result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, timeout)
            return result
        
        return wrapper
    return decorator


class UserCache:
    """User caching utilities"""
    
    @staticmethod
    def get_user_profile(user_id):
        """Get cached user profile"""
        cache_key = f'user_profile:{user_id}'
        profile_data = cache.get(cache_key)
        
        if profile_data is None:
            try:
                user = CustomUser.objects.select_related('profile').get(id=user_id)
                profile_data = {
                    'id': str(user.id),
                    'username': user.username,
                    'email': user.email,
                    'full_name': user.get_full_name(),
                    'display_name': user.profile.display_name,
                    'avatar_url': user.profile.avatar_url,
                    'bio': user.profile.bio,
                    'location': user.profile.location,
                    'is_public': user.profile.is_public,
                    'theme': user.profile.theme,
                    'timezone': user.profile.timezone,
                    'email_verified': user.email_verified,
                    'date_joined': user.date_joined.isoformat(),
                }
                cache.set(cache_key, profile_data, PROFILE_CACHE_TIMEOUT)
            except CustomUser.DoesNotExist:
                return None
        
        return profile_data
    
    @staticmethod
    def invalidate_user_cache(user_id):
        """Invalidate all cache entries for a user"""
        cache_keys = [
            f'user_profile:{user_id}',
            f'user_data:{user_id}',
            f'public_profile:{user_id}',
            f'user_stats:{user_id}',
        ]
        cache.delete_many(cache_keys)
    
    @staticmethod
    def get_public_profile(user_id):
        """Get cached public profile data"""
        cache_key = f'public_profile:{user_id}'
        profile_data = cache.get(cache_key)
        
        if profile_data is None:
            try:
                user = CustomUser.objects.select_related('profile').get(id=user_id)
                if user.profile.is_public:
                    profile_data = {
                        'username': user.username,
                        'display_name': user.profile.display_name,
                        'avatar_url': user.profile.avatar_url,
                        'bio': user.profile.bio,
                        'location': user.profile.location,
                        'website': user.profile.website,
                        'twitter': user.profile.twitter,
                        'linkedin': user.profile.linkedin,
                        'github': user.profile.github,
                        'date_joined': user.date_joined.isoformat(),
                    }
                    
                    # Filter based on privacy settings
                    if not user.profile.show_real_name:
                        profile_data.pop('full_name', None)
                        
                else:
                    # Private profile - return minimal data
                    profile_data = {
                        'username': user.username,
                        'avatar_url': user.profile.avatar_url,
                        'is_private': True
                    }
                
                cache.set(cache_key, profile_data, PROFILE_CACHE_TIMEOUT)
            except CustomUser.DoesNotExist:
                return None
        
        return profile_data
    
    @staticmethod
    def get_user_stats(user_id):
        """Get cached user statistics"""
        cache_key = f'user_stats:{user_id}'
        stats = cache.get(cache_key)
        
        if stats is None:
            try:
                user = CustomUser.objects.get(id=user_id)
                stats = {
                    'login_count': user.login_count,
                    'date_joined': user.date_joined.isoformat(),
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'email_verified': user.email_verified,
                    'is_active': user.is_active,
                }
                cache.set(cache_key, stats, USER_CACHE_TIMEOUT)
            except CustomUser.DoesNotExist:
                return None
        
        return stats


class ProfileSearchCache:
    """Profile search caching utilities"""
    
    @staticmethod
    def search_profiles(query, page=1, per_page=20):
        """Search profiles with caching"""
        cache_key = f'profile_search:{hashlib.md5(f"{query}:{page}:{per_page}".encode()).hexdigest()}'
        results = cache.get(cache_key)
        
        if results is None:
            profiles = Profile.objects.get_public_profiles().search_profiles(query)
            
            # Paginate results
            start = (page - 1) * per_page
            end = start + per_page
            paginated_profiles = profiles[start:end]
            
            results = {
                'profiles': [
                    {
                        'user_id': str(profile.user.id),
                        'username': profile.user.username,
                        'display_name': profile.display_name,
                        'avatar_url': profile.avatar_url,
                        'bio': profile.bio[:100] if profile.bio else '',
                        'location': profile.location,
                    }
                    for profile in paginated_profiles
                ],
                'total': profiles.count(),
                'page': page,
                'per_page': per_page,
            }
            
            cache.set(cache_key, results, SEARCH_CACHE_TIMEOUT)
        
        return results
    
    @staticmethod
    def invalidate_search_cache():
        """Invalidate profile search cache"""
        # This would typically use cache patterns or tags
        # For now, we'll clear specific known keys
        cache.delete_many([
            key for key in cache._cache.keys() 
            if key.startswith('profile_search:')
        ])


# Cached functions
@cache_user_data()
def get_active_users_count():
    """Get count of active users (cached)"""
    return CustomUser.objects.filter(is_active=True).count()


@cache_user_data()
def get_verified_users_count():
    """Get count of verified users (cached)"""
    return CustomUser.objects.filter(email_verified=True).count()


@cache_user_data()
def get_recent_users(limit=10):
    """Get recent users (cached)"""
    users = CustomUser.objects.filter(is_active=True).select_related('profile').order_by('-date_joined')[:limit]
    return [
        {
            'id': str(user.id),
            'username': user.username,
            'display_name': user.profile.display_name,
            'avatar_url': user.profile.avatar_url,
            'date_joined': user.date_joined.isoformat(),
        }
        for user in users
    ]


def warm_user_cache(user_id):
    """Pre-warm cache for a user"""
    UserCache.get_user_profile(user_id)
    UserCache.get_public_profile(user_id)
    UserCache.get_user_stats(user_id)