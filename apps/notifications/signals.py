# File: DjangoVerseHub/apps/notifications/signals.py
"""
Signal receivers that turn domain events into notifications.

Events covered
--------------
- Comment on an article        -> notify the article author        (type: comment)
- Reply to a comment           -> notify the parent comment author (type: comment)
- Article published            -> notify all of the author's followers (type: post)
- Follow                       -> notify the followed user         (type: follow)
- Article like  (lazy-wired)   -> notify the article author        (type: like)
- Comment like  (lazy-wired)   -> notify the comment author        (type: like)

The like receivers are connected in ``NotificationsConfig.ready`` via
``apps.get_model`` so they are a silent no-op until those models exist.

All creation goes through ``Notification.objects.notify`` which never notifies
the actor, de-duplicates unread notifications and honours in-app preferences.
Delivery (WebSocket push + optional immediate email) is done by
``dispatch_notifications``.
"""
import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.comments.models import Comment
from apps.users.models import Follow

from .models import Notification

logger = logging.getLogger(__name__)

try:  # Article is optional at import time so the app also works stand-alone.
    from apps.articles.models import Article
except Exception:  # pragma: no cover - defensive
    Article = None


# ---------------------------------------------------------------------------
# Delivery helpers
# ---------------------------------------------------------------------------
def _display_name(user):
    if user is None:
        return 'Someone'
    return user.get_full_name() or user.username


def _push_allowed(user):
    profile = getattr(user, 'profile', None)
    return profile is None or getattr(profile, 'push_notifications', True)


def send_notification_to_user(notification):
    """
    Push a notification (and the recipient's new unread count) over the
    channel layer to the recipient's personal group.

    Never raises: a missing/broken channel layer must not break the request.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer

        from .consumers import user_group_name
        from .serializers import NotificationSerializer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        recipient = notification.recipient
        if not _push_allowed(recipient):
            return

        group_name = user_group_name(recipient.pk)

        async_to_sync(channel_layer.group_send)(
            group_name,
            {'type': 'notification_message', 'notification': NotificationSerializer(notification).data},
        )
        async_to_sync(channel_layer.group_send)(
            group_name,
            {'type': 'unread_count_update', 'count': Notification.objects.unread(recipient).count()},
        )
    except Exception:  # pragma: no cover - never let delivery break the caller
        logger.exception('Real-time delivery failed for notification %s', getattr(notification, 'pk', None))


def queue_notification_email(notification):
    """Enqueue an immediate email if the recipient asked for one for this type."""
    try:
        from .models import NotificationPreference
        from .tasks import send_notification_email

        prefs = NotificationPreference.for_user(notification.recipient)
        if prefs.wants_immediate_email and prefs.allows_email(notification.notification_type):
            send_notification_email.delay(notification.pk)
    except Exception:  # pragma: no cover - broker down etc.
        logger.exception('Could not queue email for notification %s', getattr(notification, 'pk', None))


def dispatch_notifications(notifications):
    """Deliver freshly created notifications in real time (and by email if wanted)."""
    for notification in notifications:
        send_notification_to_user(notification)
        queue_notification_email(notification)
    return notifications


def notify(recipients, sender, notification_type, message, target=None, **kwargs):
    """Create + deliver in one call. Returns the created notifications."""
    created = Notification.objects.notify(
        recipients, sender, notification_type, message, target=target, **kwargs
    )
    return dispatch_notifications(created)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------
@receiver(post_save, sender=Comment, dispatch_uid='notifications.comment_created')
def create_comment_notification(sender, instance, created, **kwargs):
    """Comment -> article author; reply -> parent comment author."""
    if not created or kwargs.get('raw'):
        return

    actor = instance.author
    name = _display_name(actor)

    target = None
    try:
        target = instance.content_object
    except Exception:
        target = None

    parent = instance.parent
    parent_author = parent.author if parent is not None else None

    # Notify the content-object author (unless they are the actor or already the
    # parent author, who gets the more specific "replied" notification below).
    content_author = getattr(target, 'author', None)
    if content_author is not None and content_author != parent_author:
        title = getattr(target, 'title', None)
        message = f'{name} commented on your article "{title}".' if title else f'{name} commented on your article.'
        notify([content_author], actor, 'comment', message, target=target)

    if parent_author is not None:
        notify([parent_author], actor, 'comment', f'{name} replied to your comment.', target=parent)


# ---------------------------------------------------------------------------
# Follows
# ---------------------------------------------------------------------------
@receiver(post_save, sender=Follow, dispatch_uid='notifications.follow_created')
def create_follow_notification(sender, instance, created, **kwargs):
    if not created or kwargs.get('raw'):
        return
    follower = instance.follower
    notify(
        [instance.following], follower, 'follow',
        f'{_display_name(follower)} started following you.', target=follower,
    )


# ---------------------------------------------------------------------------
# Articles: notify followers when an article becomes published
# ---------------------------------------------------------------------------
if Article is not None:

    @receiver(pre_save, sender=Article, dispatch_uid='notifications.article_pre_save')
    def remember_previous_status(sender, instance, **kwargs):
        """Stash whether the article was already published before this save."""
        if instance._state.adding or instance.pk is None:
            instance._was_published = False
            return
        instance._was_published = (
            Article.objects.filter(pk=instance.pk, status='published').exists()
        )

    @receiver(post_save, sender=Article, dispatch_uid='notifications.article_published')
    def create_article_published_notification(sender, instance, created, **kwargs):
        if kwargs.get('raw') or instance.status != 'published':
            return
        if getattr(instance, '_was_published', False):
            return  # already published before this save: no transition
        instance._was_published = True

        author = instance.author
        followers = author.followers.filter(is_active=True)
        notify(
            followers, author, 'post',
            f'{_display_name(author)} published a new article: "{instance.title}".',
            target=instance,
        )


# ---------------------------------------------------------------------------
# Likes (connected lazily from AppConfig.ready)
# ---------------------------------------------------------------------------
def create_article_like_notification(sender, instance, created, **kwargs):
    """ArticleLike(user, article) -> notify the article author."""
    if not created or kwargs.get('raw'):
        return
    article = getattr(instance, 'article', None)
    user = getattr(instance, 'user', None)
    if article is None or user is None:
        return
    notify(
        [article.author], user, 'like',
        f'{_display_name(user)} liked your article "{article.title}".', target=article,
    )


def create_comment_like_notification(sender, instance, created, **kwargs):
    """CommentLike(user, comment) -> notify the comment author."""
    if not created or kwargs.get('raw'):
        return
    comment = getattr(instance, 'comment', None)
    user = getattr(instance, 'user', None)
    if comment is None or user is None:
        return
    notify([comment.author], user, 'like', f'{_display_name(user)} liked your comment.', target=comment)


def connect_optional_like_signals():
    """
    Wire like receivers to models that may not exist yet.
    Safe to call repeatedly thanks to dispatch_uid.
    """
    from django.apps import apps as django_apps

    for app_label, model_name, handler, uid in (
        ('articles', 'ArticleLike', create_article_like_notification, 'notifications.article_like_created'),
        ('comments', 'CommentLike', create_comment_like_notification, 'notifications.comment_like_created'),
    ):
        try:
            model = django_apps.get_model(app_label, model_name)
        except LookupError:
            continue
        post_save.connect(handler, sender=model, dispatch_uid=uid)
