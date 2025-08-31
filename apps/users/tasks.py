# File: DjangoVerseHub/apps/users/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    """Send welcome email to new user"""
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to DjangoVerseHub!'
        context = {
            'user': user,
            'site_name': 'DjangoVerseHub',
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        }
        
        html_message = render_to_string('emails/welcome.html', context)
        plain_message = render_to_string('emails/welcome.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f'Welcome email sent to {user.email}')
        
    except User.DoesNotExist:
        logger.error(f'User with id {user_id} does not exist')
    except Exception as exc:
        logger.error(f'Failed to send welcome email to user {user_id}: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, user_id, reset_url):
    """Send password reset email"""
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Reset your password - DjangoVerseHub'
        context = {
            'user': user,
            'reset_url': reset_url,
            'site_name': 'DjangoVerseHub',
        }
        
        html_message = render_to_string('emails/password_reset.html', context)
        plain_message = render_to_string('emails/password_reset.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f'Password reset email sent to {user.email}')
        
    except User.DoesNotExist:
        logger.error(f'User with id {user_id} does not exist')
    except Exception as exc:
        logger.error(f'Failed to send password reset email to user {user_id}: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=3)
def send_email_verification(self, user_id, verification_url):
    """Send email verification email"""
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Verify your email - DjangoVerseHub'
        context = {
            'user': user,
            'verification_url': verification_url,
            'site_name': 'DjangoVerseHub',
        }
        
        html_message = render_to_string('emails/email_verification.html', context)
        plain_message = render_to_string('emails/email_verification.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        
        logger.info(f'Email verification sent to {user.email}')
        
    except User.DoesNotExist:
        logger.error(f'User with id {user_id} does not exist')
    except Exception as exc:
        logger.error(f'Failed to send email verification to user {user_id}: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task
def cleanup_unverified_users():
    """Clean up unverified users older than 7 days"""
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=7)
    unverified_users = User.objects.filter(
        is_verified=False,
        date_joined__lt=cutoff_date
    )
    
    count = unverified_users.count()
    unverified_users.delete()
    
    logger.info(f'Cleaned up {count} unverified users')
    return count