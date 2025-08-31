# File: DjangoVerseHub/django_verse_hub/utils.py

import uuid
import hashlib
from django.utils.text import slugify
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def generate_unique_slug(instance, field_name, slug_field='slug'):
    """
    Generate a unique slug for a model instance.
    """
    slug = slugify(getattr(instance, field_name))
    unique_slug = slug
    num = 1
    
    while instance.__class__.objects.filter(**{slug_field: unique_slug}).exists():
        unique_slug = f'{slug}-{num}'
        num += 1
    
    return unique_slug


def get_client_ip(request):
    """
    Get the client's IP address from the request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def cache_key_generator(*args, **kwargs):
    """
    Generate a cache key from arguments.
    """
    key_parts = [str(arg) for arg in args]
    key_parts.extend([f"{k}:{v}" for k, v in sorted(kwargs.items())])
    key_string = ':'.join(key_parts)
    
    # Hash the key if it's too long
    if len(key_string) > 200:
        return hashlib.md5(key_string.encode()).hexdigest()
    
    return key_string


def send_notification_email(user, subject, template_name, context=None):
    """
    Send a notification email to a user.
    """
    if not context:
        context = {}
    
    context.update({
        'user': user,
        'site_name': 'DjangoVerseHub',
        'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
    })
    
    html_message = render_to_string(template_name, context)
    plain_message = render_to_string(
        template_name.replace('.html', '.txt'), 
        context
    )
    
    send_mail(
        subject=subject,
        message=plain_message,
        html_message=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def get_or_create_cache(cache_key, callable_func, timeout=300):
    """
    Get data from cache or create it using the callable function.
    """
    data = cache.get(cache_key)
    if data is None:
        data = callable_func()
        cache.set(cache_key, data, timeout)
    return data


def upload_to_path(instance, filename):
    """
    Generate upload path for file fields.
    """
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return f"{instance._meta.app_label}/{instance._meta.model_name}/{filename}"


class PaginationMixin:
    """
    Mixin to add pagination helpers to views.
    """
    
    def get_page_range(self, page, num_pages, display_pages=7):
        """
        Get a range of pages to display in pagination.
        """
        half = display_pages // 2
        
        if num_pages <= display_pages:
            return range(1, num_pages + 1)
        
        if page <= half:
            return range(1, display_pages + 1)
        
        if page > num_pages - half:
            return range(num_pages - display_pages + 1, num_pages + 1)
        
        return range(page - half, page + half + 1)