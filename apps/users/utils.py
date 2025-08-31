# File: DjangoVerseHub/apps/users/utils.py

import os
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.urls import reverse
from django.contrib.sites.models import Site
from django.utils.crypto import get_random_string
from PIL import Image
from io import BytesIO


def generate_username(email):
    """Generate a unique username from email"""
    base_username = email.split('@')[0]
    username = base_username
    
    # Import here to avoid circular imports
    from .models import CustomUser
    
    counter = 1
    while CustomUser.objects.filter(username=username).exists():
        username = f"{base_username}{counter}"
        counter += 1
    
    return username


def upload_avatar_path(instance, filename):
    """Generate upload path for user avatars"""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('avatars', str(instance.user.id), filename)


def upload_cover_path(instance, filename):
    """Generate upload path for cover images"""
    ext = filename.split('.')[-1]
    filename = f'{uuid.uuid4()}.{ext}'
    return os.path.join('covers', str(instance.user.id), filename)


def resize_image(image_path, size=(300, 300), quality=85):
    """Resize image to specified dimensions"""
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save the resized image
            output = BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            
            with open(image_path, 'wb') as f:
                f.write(output.getvalue())
        
        return True
    except Exception as e:
        print(f"Error resizing image: {e}")
        return False


def generate_verification_token():
    """Generate a secure verification token"""
    return secrets.token_urlsafe(32)


def send_verification_email(user):
    """Send email verification email to user"""
    if not user.email:
        return False
    
    # Generate verification token (this would typically be stored in DB)
    token = generate_verification_token()
    
    # Get current site
    current_site = Site.objects.get_current()
    
    # Build verification URL
    verification_url = f"http://{current_site.domain}{reverse('users:verify_email', kwargs={'token': token})}"
    
    # Email context
    context = {
        'user': user,
        'verification_url': verification_url,
        'site_name': current_site.name,
    }
    
    # Render email templates
    subject = f'Verify your email address - {current_site.name}'
    html_message = render_to_string('users/emails/verify_email.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False


def send_welcome_email(user):
    """Send welcome email to new user"""
    if not user.email:
        return False
    
    # Get current site
    current_site = Site.objects.get_current()
    
    # Email context
    context = {
        'user': user,
        'site_name': current_site.name,
        'site_url': f"http://{current_site.domain}",
        'login_url': f"http://{current_site.domain}{reverse('users:login')}",
        'profile_url': f"http://{current_site.domain}{reverse('users:profile', kwargs={'pk': user.pk})}",
    }
    
    # Render email templates
    subject = f'Welcome to {current_site.name}!'
    html_message = render_to_string('users/emails/welcome.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending welcome email: {e}")
        return False


def send_password_reset_email(user, reset_token):
    """Send password reset email"""
    if not user.email:
        return False
    
    # Get current site
    current_site = Site.objects.get_current()
    
    # Build reset URL
    reset_url = f"http://{current_site.domain}{reverse('users:password_reset_confirm', kwargs={'token': reset_token})}"
    
    # Email context
    context = {
        'user': user,
        'reset_url': reset_url,
        'site_name': current_site.name,
    }
    
    # Render email templates
    subject = f'Password Reset - {current_site.name}'
    html_message = render_to_string('users/emails/password_reset.html', context)
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False


def validate_username(username):
    """Validate username according to rules"""
    import re
    
    # Check length
    if len(username) < 3 or len(username) > 30:
        return False, "Username must be between 3 and 30 characters."
    
    # Check format (alphanumeric, underscores, hyphens)
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, underscores, and hyphens."
    
    # Check prohibited usernames
    prohibited = [
        'admin', 'administrator', 'root', 'api', 'www', 'mail',
        'support', 'help', 'info', 'contact', 'about', 'blog',
        'news', 'team', 'staff', 'mod', 'moderator', 'null',
        'undefined', 'delete', 'edit', 'create', 'update'
    ]
    
    if username.lower() in prohibited:
        return False, "This username is not allowed."
    
    # Check for consecutive special characters
    if '__' in username or '--' in username or '_-' in username or '-_' in username:
        return False, "Username cannot contain consecutive special characters."
    
    # Check start/end with special characters
    if username.startswith(('_', '-')) or username.endswith(('_', '-')):
        return False, "Username cannot start or end with special characters."
    
    return True, "Username is valid."


def get_user_ip(request):
    """Get user's IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_client_info(request):
    """Get client information from request"""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Basic user agent parsing
    info = {
        'user_agent': user_agent,
        'ip_address': get_user_ip(request),
        'is_mobile': 'Mobile' in user_agent or 'Android' in user_agent or 'iPhone' in user_agent,
        'browser': 'Unknown',
        'os': 'Unknown'
    }
    
    # Simple browser detection
    if 'Chrome' in user_agent:
        info['browser'] = 'Chrome'
    elif 'Firefox' in user_agent:
        info['browser'] = 'Firefox'
    elif 'Safari' in user_agent:
        info['browser'] = 'Safari'
    elif 'Edge' in user_agent:
        info['browser'] = 'Edge'
    
    # Simple OS detection
    if 'Windows' in user_agent:
        info['os'] = 'Windows'
    elif 'Mac' in user_agent:
        info['os'] = 'MacOS'
    elif 'Linux' in user_agent:
        info['os'] = 'Linux'
    elif 'Android' in user_agent:
        info['os'] = 'Android'
    elif 'iPhone' in user_agent or 'iPad' in user_agent:
        info['os'] = 'iOS'
    
    return info


def generate_api_key():
    """Generate API key for user"""
    return f"dvh_{get_random_string(32)}"


def hash_api_key(api_key):
    """Hash API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_user_directory(user):
    """Create user-specific directories"""
    user_dir = os.path.join(settings.MEDIA_ROOT, 'users', str(user.id))
    
    directories = ['avatars', 'covers', 'uploads', 'documents']
    
    for directory in directories:
        dir_path = os.path.join(user_dir, directory)
        os.makedirs(dir_path, exist_ok=True)
    
    return user_dir


def cleanup_user_files(user):
    """Clean up all files for a user"""
    import shutil
    
    user_dir = os.path.join(settings.MEDIA_ROOT, 'users', str(user.id))
    
    if os.path.exists(user_dir):
        try:
            shutil.rmtree(user_dir)
            return True
        except Exception as e:
            print(f"Error cleaning up user files: {e}")
            return False
    
    return True


class UserStatsCalculator:
    """Calculate various user statistics"""
    
    @staticmethod
    def get_user_activity_stats(user, days=30):
        """Get user activity statistics for specified days"""
        from datetime import datetime, timedelta
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # This would integrate with activity tracking
        stats = {
            'login_count': user.login_count,
            'profile_views': 0,  # Would track in separate model
            'content_created': 0,  # Would count articles, comments, etc.
            'last_active': user.last_login,
            'activity_score': 0,  # Calculated activity score
        }
        
        return stats
    
    @staticmethod
    def calculate_profile_completion(profile):
        """Calculate profile completion percentage"""
        fields = [
            'full_name', 'bio', 'avatar', 'location', 
            'website', 'twitter', 'linkedin', 'github'
        ]
        
        completed = 0
        for field in fields:
            if getattr(profile, field, None):
                completed += 1
        
        # Add user fields
        user_fields = ['first_name', 'last_name', 'phone_number', 'date_of_birth']
        for field in user_fields:
            if getattr(profile.user, field, None):
                completed += 1
        
        total_fields = len(fields) + len(user_fields)
        return (completed / total_fields) * 100