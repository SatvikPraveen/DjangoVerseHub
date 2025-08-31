# File: DjangoVerseHub/apps/comments/tasks.py

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.contrib.auth import get_user_model
import logging
import re

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_comment_notification(self, comment_id, recipient_id, is_reply=False):
    """Send email notification for new comment"""
    try:
        from .models import Comment
        
        comment = Comment.objects.select_related('author', 'content_type').get(id=comment_id)
        recipient = User.objects.get(id=recipient_id)
        
        # Check if recipient wants notifications
        if hasattr(recipient, 'profile') and not recipient.profile.email_notifications:
            return
        
        subject_type = 'reply' if is_reply else 'comment'
        subject = f'New {subject_type} on your {"comment" if is_reply else "article"}'
        
        context = {
            'comment': comment,
            'recipient': recipient,
            'is_reply': is_reply,
            'site_name': 'DjangoVerseHub',
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
            'comment_url': comment.get_absolute_url(),
        }
        
        html_message = render_to_string('emails/comment_notification.html', context)
        plain_message = render_to_string('emails/comment_notification.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
        
        logger.info(f'Comment notification sent to {recipient.email}')
        
    except Exception as exc:
        logger.error(f'Failed to send comment notification: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task(bind=True, max_retries=3)
def send_comment_like_notification(self, comment_id, liker_id):
    """Send notification when comment is liked"""
    try:
        from .models import Comment
        
        comment = Comment.objects.select_related('author').get(id=comment_id)
        liker = User.objects.get(id=liker_id)
        
        # Check if comment author wants notifications
        if hasattr(comment.author, 'profile') and not comment.author.profile.email_notifications:
            return
        
        context = {
            'comment': comment,
            'liker': liker,
            'site_name': 'DjangoVerseHub',
            'comment_url': comment.get_absolute_url(),
        }
        
        html_message = render_to_string('emails/comment_like_notification.html', context)
        plain_message = render_to_string('emails/comment_like_notification.txt', context)
        
        send_mail(
            subject='Someone liked your comment',
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[comment.author.email],
            fail_silently=False,
        )
        
        logger.info(f'Comment like notification sent to {comment.author.email}')
        
    except Exception as exc:
        logger.error(f'Failed to send comment like notification: {exc}')
        raise self.retry(countdown=60, exc=exc)


@shared_task
def moderate_comment(comment_id):
    """Auto-moderate comment for spam/inappropriate content"""
    try:
        from .models import Comment
        
        comment = Comment.objects.get(id=comment_id)
        
        # Basic auto-moderation checks
        should_flag = False
        
        # Check for spam patterns
        spam_patterns = [
            r'https?://[^\s]+',  # URLs
            r'www\.[^\s]+',
            r'\b(buy|sale|discount|offer|free|win|prize)\b',  # Common spam words
            r'(.)\1{4,}',  # Repeated characters
        ]
        
        content_lower = comment.content.lower()
        for pattern in spam_patterns:
            if re.search(pattern, content_lower):
                should_flag = True
                break
        
        # Check for excessive caps (more than 80% uppercase)
        if len(re.findall(r'[A-Z]', comment.content)) / max(len(comment.content), 1) > 0.8:
            should_flag = True
        
        # Check for inappropriate language
        inappropriate_words = [
            'spam', 'scam', 'fake', 'stupid', 'idiot'  # Add more as needed
        ]
        
        for word in inappropriate_words:
            if word in content_lower:
                should_flag = True
                break
        
        if should_flag:
            comment.flag()
            logger.info(f'Comment {comment_id} flagged by auto-moderation')
        
    except Exception as e:
        logger.error(f'Failed to moderate comment {comment_id}: {e}')


@shared_task
def cleanup_old_flagged_comments():
    """Clean up old flagged comments"""
    from .models import Comment
    from django.utils import timezone
    from datetime import timedelta
    
    try:
        # Delete flagged comments older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        old_flagged = Comment.objects.filter(
            is_flagged=True,
            created_at__lt=cutoff_date
        )
        
        count = old_flagged.count()
        old_flagged.delete()
        
        logger.info(f'Cleaned up {count} old flagged comments')
        return count
        
    except Exception as e:
        logger.error(f'Failed to cleanup old flagged comments: {e}')


@shared_task
def send_daily_comment_digest():
    """Send daily digest of comments to moderators"""
    try:
        from .models import Comment
        from django.utils import timezone
        from datetime import timedelta
        
        # Get staff users who want notifications
        staff_users = User.objects.filter(is_staff=True, is_active=True)
        
        yesterday = timezone.now() - timedelta(days=1)
        
        # Get yesterday's comment stats
        new_comments = Comment.objects.filter(created_at__gte=yesterday).count()
        flagged_comments = Comment.objects.filter(is_flagged=True, created_at__gte=yesterday).count()
        
        if new_comments == 0 and flagged_comments == 0:
            return  # No need to send digest
        
        context = {
            'new_comments': new_comments,
            'flagged_comments': flagged_comments,
            'date': yesterday.date(),
            'site_name': 'DjangoVerseHub',
        }
        
        html_message = render_to_string('emails/comment_digest.html', context)
        plain_message = render_to_string('emails/comment_digest.txt', context)
        
        for staff_user in staff_users:
            send_mail(
                subject='Daily Comment Digest - DjangoVerseHub',
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[staff_user.email],
                fail_silently=True,
            )
        
        logger.info(f'Daily comment digest sent to {staff_users.count()} staff users')
        
    except Exception as e:
        logger.error(f'Failed to send daily comment digest: {e}')