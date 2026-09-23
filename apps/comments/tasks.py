# File: DjangoVerseHub/apps/comments/tasks.py

import logging
from datetime import timedelta
from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .moderation import should_flag

User = get_user_model()
logger = logging.getLogger(__name__)

SITE_NAME = "DjangoVerseHub"

# Only transport-level failures are worth retrying; data or template errors
# would fail identically on every attempt (and, with eager Celery, would
# bubble up into the request that created the comment).
RETRYABLE_ERRORS = (SMTPException, ConnectionError, TimeoutError, OSError)


def _site_url():
    return getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")


def _absolute_url(path):
    if not path:
        return _site_url()
    if path.startswith(("http://", "https://")):
        return path
    return f"{_site_url()}{path}"


def _display_name(user):
    return user.get_full_name() or user.username or user.email


def _wants_email(user):
    """Active user with an address who has not opted out of email notifications."""
    if user is None or not user.is_active or not user.email:
        return False
    profile = getattr(user, "profile", None)
    return not (profile is not None and not getattr(profile, "email_notifications", True))


def _target_title(obj):
    if obj is None:
        return "a post"
    return getattr(obj, "title", None) or str(obj)


def build_comment_email_context(comment, recipient, **extra):
    """Context shared by the comment email templates."""
    target = comment.content_object
    context = {
        "site_name": SITE_NAME,
        "site_url": _site_url(),
        "comment": comment,
        "commenter": comment.author,
        "commenter_name": _display_name(comment.author),
        "recipient": recipient,
        "recipient_name": _display_name(recipient),
        "target": target,
        "target_title": _target_title(target),
        "comment_url": _absolute_url(comment.get_absolute_url()),
    }
    context.update(extra)
    return context


def _deliver(task, subject, template, context, recipient):
    """Render both template flavours and send; retry only on transport errors."""
    html_message = render_to_string(f"emails/{template}.html", context)
    plain_message = render_to_string(f"emails/{template}.txt", context)
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient.email],
            fail_silently=False,
        )
    except RETRYABLE_ERRORS as exc:
        logger.warning("Email delivery to %s failed, retrying: %s", recipient.email, exc)
        raise task.retry(countdown=60, exc=exc)
    return True


@shared_task(bind=True, max_retries=3)
def send_comment_notification(self, comment_id, recipient_id, is_reply=False):
    """Email ``recipient`` about a new comment (or reply to their comment)."""
    from .models import Comment

    comment = Comment.objects.select_related("author", "content_type").filter(id=comment_id).first()
    recipient = User.objects.select_related("profile").filter(id=recipient_id).first()
    if comment is None or recipient is None:
        logger.info("Comment notification skipped: comment=%s recipient=%s missing", comment_id, recipient_id)
        return False
    if recipient.pk == comment.author_id or not _wants_email(recipient):
        return False

    context = build_comment_email_context(comment, recipient, is_reply=is_reply)
    if is_reply:
        subject = f"{context['commenter_name']} replied to your comment"
    else:
        subject = f'New comment on "{context["target_title"]}"'

    _deliver(self, subject, "comment_notification", context, recipient)
    logger.info("Comment notification sent to %s", recipient.email)
    return True


@shared_task(bind=True, max_retries=3)
def send_comment_like_notification(self, comment_id, liker_id):
    """Email the comment author when someone likes their comment."""
    from .models import Comment

    comment = Comment.objects.select_related("author", "author__profile", "content_type").filter(id=comment_id).first()
    liker = User.objects.filter(id=liker_id).first()
    if comment is None or liker is None:
        logger.info("Like notification skipped: comment=%s liker=%s missing", comment_id, liker_id)
        return False
    recipient = comment.author
    if liker.pk == recipient.pk or not _wants_email(recipient):
        return False

    context = build_comment_email_context(comment, recipient, liker=liker, liker_name=_display_name(liker))
    _deliver(self, f"{context['liker_name']} liked your comment", "comment_like_notification", context, recipient)
    logger.info("Comment like notification sent to %s", recipient.email)
    return True


@shared_task
def moderate_comment(comment_id):
    """Flag a new comment for review when it looks like spam or abuse."""
    from .models import Comment

    comment = Comment.objects.filter(id=comment_id).first()
    if comment is None:
        return False
    if should_flag(comment.content):
        comment.flag()
        logger.info("Comment %s flagged by auto-moderation", comment_id)
        return True
    return False


@shared_task
def cleanup_old_flagged_comments(days=30):
    """
    Permanently delete comments that moderators have hidden (is_active=False)
    and that are still flagged, once they are older than ``days``.

    Comments that are merely flagged but not yet reviewed are left alone.
    """
    from .models import Comment

    cutoff = timezone.now() - timedelta(days=days)
    count, _ = Comment.objects.filter(is_flagged=True, is_active=False, updated_at__lt=cutoff).delete()
    logger.info("Cleaned up %s old hidden flagged comments", count)
    return count


@shared_task
def send_daily_comment_digest():
    """Send a daily digest of comment activity to staff users."""
    from .models import Comment

    since = timezone.now() - timedelta(days=1)
    new_comments = Comment.objects.filter(created_at__gte=since).count()
    flagged_comments = Comment.objects.filter(is_flagged=True, created_at__gte=since).count()
    pending_review = Comment.objects.filter(is_flagged=True, is_active=True).count()

    if new_comments == 0 and flagged_comments == 0 and pending_review == 0:
        return 0

    context = {
        "new_comments": new_comments,
        "flagged_comments": flagged_comments,
        "pending_review": pending_review,
        "date": since.date(),
        "site_name": SITE_NAME,
        "site_url": _site_url(),
    }
    html_message = render_to_string("emails/comment_digest.html", context)
    plain_message = render_to_string("emails/comment_digest.txt", context)

    staff_emails = list(
        User.objects.filter(is_staff=True, is_active=True).exclude(email="").values_list("email", flat=True)
    )
    sent = 0
    for email in staff_emails:
        try:
            send_mail(
                subject=f"Daily Comment Digest - {SITE_NAME}",
                message=plain_message,
                html_message=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            sent += 1
        except RETRYABLE_ERRORS as exc:
            logger.warning("Digest delivery to %s failed: %s", email, exc)

    logger.info("Daily comment digest sent to %s staff users", sent)
    return sent
