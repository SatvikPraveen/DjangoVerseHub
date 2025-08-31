# File: DjangoVerseHub/apps/api/throttling.py

from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from django.core.cache import cache


class CustomUserRateThrottle(UserRateThrottle):
    """Custom user rate throttle with enhanced features"""
    scope = 'user'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

    def allow_request(self, request, view):
        # Staff users get higher limits
        if request.user.is_authenticated and request.user.is_staff:
            self.rate = '5000/hour'
        
        return super().allow_request(request, view)


class CustomAnonRateThrottle(AnonRateThrottle):
    """Custom anonymous rate throttle"""
    scope = 'anon'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class LoginRateThrottle(UserRateThrottle):
    """Rate throttle for login attempts"""
    scope = 'login'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class BurstRateThrottle(UserRateThrottle):
    """Burst rate throttle for short-term limits"""
    scope = 'burst'


class SustainedRateThrottle(UserRateThrottle):
    """Sustained rate throttle for long-term limits"""
    scope = 'sustained'


class APIKeyRateThrottle(UserRateThrottle):
    """Rate throttle for API key users"""
    scope = 'api_key'

    def get_cache_key(self, request, view):
        api_key = request.META.get('HTTP_X_API_KEY')
        if not api_key:
            return None

        return self.cache_format % {
            'scope': self.scope,
            'ident': api_key
        }


class CreateArticleRateThrottle(UserRateThrottle):
    """Rate throttle for article creation"""
    scope = 'create_article'


class CreateCommentRateThrottle(UserRateThrottle):
    """Rate throttle for comment creation"""
    scope = 'create_comment'


class SearchRateThrottle(UserRateThrottle):
    """Rate throttle for search operations"""
    scope = 'search'


class UploadRateThrottle(UserRateThrottle):
    """Rate throttle for file uploads"""
    scope = 'upload'


class AdminAPIRateThrottle(UserRateThrottle):
    """Rate throttle for admin API operations"""
    scope = 'admin_api'

    def allow_request(self, request, view):
        # Only apply to staff users
        if not (request.user.is_authenticated and request.user.is_staff):
            return True
        
        return super().allow_request(request, view)


class PasswordResetRateThrottle(AnonRateThrottle):
    """Rate throttle for password reset requests"""
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        # Use email from request data if available
        email = request.data.get('email') if hasattr(request, 'data') else None
        if email:
            ident = email
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class RegistrationRateThrottle(AnonRateThrottle):
    """Rate throttle for user registration"""
    scope = 'registration'


class EmailVerificationRateThrottle(UserRateThrottle):
    """Rate throttle for email verification requests"""
    scope = 'email_verification'


class ContactFormRateThrottle(AnonRateThrottle):
    """Rate throttle for contact form submissions"""
    scope = 'contact_form'