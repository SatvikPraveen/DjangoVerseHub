# File: DjangoVerseHub/apps/notifications/models.py
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone


# ---------------------------------------------------------------------------
# Notification types
# ---------------------------------------------------------------------------
NOTIFICATION_TYPES = [
    ('like', 'Like'),
    ('comment', 'Comment'),
    ('follow', 'Follow'),
    ('mention', 'Mention'),
    ('post', 'New Post'),
    ('system', 'System'),
]

# Types a user can opt in/out of. 'system' notifications are always delivered.
CONFIGURABLE_TYPES = ['like', 'comment', 'follow', 'mention', 'post']

# Presentation hints used by the navbar dropdown and the JS client.
TYPE_ICONS = {
    'like': 'heart-fill',
    'comment': 'chat-fill',
    'follow': 'person-plus-fill',
    'mention': 'at',
    'post': 'file-earmark-text-fill',
    'system': 'gear-fill',
}
TYPE_COLORS = {
    'like': 'danger',
    'comment': 'primary',
    'follow': 'success',
    'mention': 'warning',
    'post': 'info',
    'system': 'secondary',
}


# ---------------------------------------------------------------------------
# QuerySet / Manager
# ---------------------------------------------------------------------------
class NotificationQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(recipient=user)

    def unread(self):
        return self.filter(is_read=False)

    def read(self):
        return self.filter(is_read=True)

    def of_type(self, notification_type):
        return self.filter(notification_type=notification_type)

    def with_related(self):
        """Everything a list page needs without per-row queries."""
        return self.select_related('sender', 'sender__profile', 'content_type')

    def mark_all_read(self):
        """Mark every unread notification in this queryset as read. Returns count."""
        return self.unread().update(is_read=True, read_at=timezone.now())


class NotificationManager(models.Manager.from_queryset(NotificationQuerySet)):
    def unread(self, user=None):
        qs = self.get_queryset().unread()
        return qs.filter(recipient=user) if user is not None else qs

    def mark_all_read(self, user):
        """Mark all of `user`'s unread notifications as read. Returns count."""
        return self.get_queryset().for_user(user).mark_all_read()

    def notify(self, recipients, sender, notification_type, message, target=None,
               dedupe=True, respect_preferences=True):
        """
        Bulk-create one notification per recipient.

        - `recipients` may be a single user, an iterable of users, or a queryset.
        - The sender is never notified about their own action.
        - With `dedupe`, a recipient who already has an *unread* notification of the
          same type, from the same sender, about the same target is skipped.
        - With `respect_preferences`, recipients who disabled in-app delivery for
          this type are skipped ('system' cannot be disabled).

        Returns the list of created Notification instances (pks populated).
        """
        if recipients is None:
            return []
        if hasattr(recipients, 'pk') and not hasattr(recipients, '__iter__'):
            recipients = [recipients]

        recipients = list(recipients)
        sender_id = getattr(sender, 'pk', None)

        # Never notify yourself; drop duplicates in the recipient list.
        seen = set()
        unique = []
        for user in recipients:
            if user is None or user.pk == sender_id or user.pk in seen:
                continue
            seen.add(user.pk)
            unique.append(user)
        if not unique:
            return []

        content_type = None
        object_id = None
        if target is not None:
            content_type = ContentType.objects.get_for_model(target)
            object_id = str(target.pk)

        if respect_preferences and notification_type in CONFIGURABLE_TYPES:
            blocked = set(
                NotificationPreference.objects.filter(
                    user__in=unique, **{f'in_app_{notification_type}': False}
                ).values_list('user_id', flat=True)
            )
            unique = [u for u in unique if u.pk not in blocked]
            if not unique:
                return []

        if dedupe:
            existing = set(
                self.get_queryset().filter(
                    recipient__in=unique,
                    sender_id=sender_id,
                    notification_type=notification_type,
                    content_type=content_type,
                    object_id=object_id,
                    is_read=False,
                ).values_list('recipient_id', flat=True)
            )
            unique = [u for u in unique if u.pk not in existing]
            if not unique:
                return []

        objs = [
            self.model(
                recipient=user,
                sender=sender,
                notification_type=notification_type,
                message=message,
                content_type=content_type,
                object_id=object_id,
            )
            for user in unique
        ]
        return self.bulk_create(objs)


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
class Notification(models.Model):
    NOTIFICATION_TYPES = NOTIFICATION_TYPES

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='sent_notifications', null=True, blank=True,
    )
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    message = models.TextField()

    # Generic foreign key for related object (CharField supports both int and UUID PKs)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationManager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['is_read', 'created_at']),
        ]

    def __str__(self):
        return f'{self.notification_type} notification for {self.recipient.username}'

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def mark_as_unread(self):
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save(update_fields=['is_read', 'read_at'])

    # -- presentation helpers (used by templates and the serializer) ----------
    @property
    def read(self):
        """Alias so templates can use `notification.read` as well as `is_read`."""
        return self.is_read

    @property
    def icon(self):
        return TYPE_ICONS.get(self.notification_type, 'bell-fill')

    @property
    def color(self):
        return TYPE_COLORS.get(self.notification_type, 'primary')

    @property
    def target(self):
        """The related object, or None if it no longer exists."""
        if self.content_type_id is None or not self.object_id:
            return None
        try:
            return self.content_object
        except Exception:
            return None

    @property
    def url(self):
        """Where clicking the notification should take the user."""
        target = self.target
        get_url = getattr(target, 'get_absolute_url', None)
        if callable(get_url):
            try:
                return get_url()
            except Exception:
                pass
        return reverse('notifications:list')


# ---------------------------------------------------------------------------
# Per-user preferences
# ---------------------------------------------------------------------------
class NotificationPreference(models.Model):
    """
    One row per user controlling how each notification type is delivered.

    - `in_app_*` : create the notification at all (shown in the list / navbar / WS).
    - `email_*`  : include the type in email delivery (immediate when
                   `digest_frequency == 'none'`, otherwise batched into the digest).
    - `Profile.email_notifications` remains the master switch for any email.
    """

    DIGEST_NONE = 'none'
    DIGEST_DAILY = 'daily'
    DIGEST_WEEKLY = 'weekly'
    DIGEST_CHOICES = [
        (DIGEST_NONE, 'Never (send each email immediately)'),
        (DIGEST_DAILY, 'Daily digest'),
        (DIGEST_WEEKLY, 'Weekly digest'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences'
    )

    in_app_like = models.BooleanField('Likes (in-app)', default=True)
    in_app_comment = models.BooleanField('Comments and replies (in-app)', default=True)
    in_app_follow = models.BooleanField('New followers (in-app)', default=True)
    in_app_mention = models.BooleanField('Mentions (in-app)', default=True)
    in_app_post = models.BooleanField('New posts from people you follow (in-app)', default=True)

    email_like = models.BooleanField('Likes (email)', default=False)
    email_comment = models.BooleanField('Comments and replies (email)', default=True)
    email_follow = models.BooleanField('New followers (email)', default=True)
    email_mention = models.BooleanField('Mentions (email)', default=True)
    email_post = models.BooleanField('New posts from people you follow (email)', default=False)

    digest_frequency = models.CharField(max_length=10, choices=DIGEST_CHOICES, default=DIGEST_DAILY)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Notification preference'
        verbose_name_plural = 'Notification preferences'

    def __str__(self):
        return f'Notification preferences for {self.user.username}'

    @classmethod
    def for_user(cls, user):
        prefs, _ = cls.objects.get_or_create(user=user)
        return prefs

    def allows_in_app(self, notification_type):
        if notification_type not in CONFIGURABLE_TYPES:
            return True
        return getattr(self, f'in_app_{notification_type}', True)

    def allows_email(self, notification_type):
        profile = getattr(self.user, 'profile', None)
        if profile is not None and not profile.email_notifications:
            return False
        if notification_type not in CONFIGURABLE_TYPES:
            return True
        return getattr(self, f'email_{notification_type}', False)

    @property
    def wants_immediate_email(self):
        return self.digest_frequency == self.DIGEST_NONE

    def email_types(self):
        """Notification types this user wants by email (ignoring the master switch)."""
        return [t for t in CONFIGURABLE_TYPES if getattr(self, f'email_{t}', False)] + ['system']
