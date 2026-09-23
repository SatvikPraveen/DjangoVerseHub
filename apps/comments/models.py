# File: DjangoVerseHub/apps/comments/models.py

import uuid
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

User = get_user_model()

# Maximum nesting depth of a thread. Root comments have depth 0, so with
# MAX_THREAD_DEPTH = 3 a thread is root -> reply -> reply -> reply.
MAX_THREAD_DEPTH = getattr(settings, 'COMMENTS_MAX_THREAD_DEPTH', 3)


def get_flag_threshold():
    """Distinct users that must flag a comment before it is marked flagged."""
    return getattr(settings, 'COMMENTS_FLAG_THRESHOLD', 3)

# Authors may edit their own comment for this long after posting.
EDIT_WINDOW = timedelta(minutes=getattr(settings, 'COMMENTS_EDIT_WINDOW_MINUTES', 15))

REMOVED_PLACEHOLDER = '[removed]'


def target_accepts_comments(obj):
    """
    Whether ``obj`` currently accepts new comments.

    Honours an ``allow_comments`` flag and a ``status`` field with a
    'published' value when the target model defines them.
    """
    if obj is None:
        return False
    if not getattr(obj, 'allow_comments', True):
        return False
    status = getattr(obj, 'status', None)
    if status is not None and status != 'published':
        return False
    return True


def build_comment_tree(comments):
    """
    Build a nested tree from a flat iterable of comments in one pass.

    Every comment gets a ``child_nodes`` list and an ``is_placeholder`` flag.
    Inactive comments are kept only when they have an active descendant, in
    which case they render as a "[removed]" placeholder; otherwise they are
    pruned together with their (inactive) subtree.

    Returns the list of root nodes, ordered by ``created_at``.
    """
    comments = sorted(comments, key=lambda c: c.created_at)
    by_id = {}
    children = defaultdict(list)
    for comment in comments:
        comment.child_nodes = []
        comment.is_placeholder = False
        by_id[comment.id] = comment
        children[comment.parent_id].append(comment)

    def attach(node):
        """Attach visible children to ``node`` and report whether it is visible."""
        visible_children = []
        for child in children.get(node.id, ()):
            if attach(child):
                visible_children.append(child)
        node.child_nodes = visible_children
        node._total_replies = sum(1 + c._total_replies for c in visible_children)
        if node.is_active:
            return True
        if visible_children:
            node.is_placeholder = True
            return True
        return False

    roots = []
    for node in children.get(None, ()):
        if attach(node):
            roots.append(node)
    # Replies whose parent is not part of the set (e.g. a filtered list)
    # are treated as roots so nothing silently disappears.
    for parent_id, nodes in children.items():
        if parent_id is not None and parent_id not in by_id:
            roots.extend(n for n in nodes if attach(n))
    return roots


def annotate_total_replies(comments):
    """
    Set ``_total_replies`` on each comment in ``comments`` (any objects, any
    mix of targets) using a single query, so ``Comment.total_replies`` does
    not hit the database once per row on list pages.
    """
    comments = list(comments)
    if not comments:
        return comments
    targets = {(c.content_type_id, str(c.object_id)) for c in comments}
    rows = Comment.objects.filter(
        is_active=True,
        content_type_id__in={ct for ct, _ in targets},
        object_id__in={oid for _, oid in targets},
    ).values_list('id', 'parent_id')
    children = defaultdict(list)
    for comment_id, parent_id in rows:
        children[parent_id].append(comment_id)
    for comment in comments:
        count = 0
        stack = [comment.id]
        while stack:
            for child_id in children.get(stack.pop(), ()):
                count += 1
                stack.append(child_id)
        comment._total_replies = count
    return comments


class CommentQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def for_object(self, obj):
        content_type = ContentType.objects.get_for_model(obj)
        return self.filter(content_type=content_type, object_id=str(obj.pk))

    def with_author(self):
        return self.select_related('author', 'author__profile')


class CommentManager(models.Manager.from_queryset(CommentQuerySet)):
    """Custom manager for Comment model"""

    def active(self):
        """Return only active comments"""
        return self.get_queryset().active()

    def for_object(self, obj):
        """Get active comments for a specific object"""
        return self.get_queryset().for_object(obj).active()

    def root_comments(self):
        """Get only root level comments (no parent)"""
        return self.filter(parent=None)

    def thread_comments(self, parent_comment):
        """Get all direct replies of a comment"""
        return self.filter(parent=parent_comment)

    def tree_for_object(self, obj):
        """
        Return the comment tree for ``obj`` as a list of root nodes.

        Fetches every comment on the object in a single query (including
        inactive ones so removed comments with replies can be shown as a
        placeholder) and builds the tree in Python.
        """
        comments = self.get_queryset().for_object(obj).with_author()
        return build_comment_tree(comments)


class Comment(models.Model):
    """Threaded comment model for any content type"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Generic foreign key to allow comments on any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField(db_index=True, help_text='Primary key of the target; all commentable models use UUID keys.')
    content_object = GenericForeignKey('content_type', 'object_id')

    # Comment details
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('author')
    )
    content = models.TextField(_('content'), max_length=1000)

    # Threading support
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies',
        verbose_name=_('parent comment')
    )
    # Denormalised nesting level (0 = root). Maintained in save().
    depth = models.PositiveSmallIntegerField(_('depth'), default=0, editable=False)

    # Status and moderation
    is_active = models.BooleanField(_('active'), default=True)
    is_flagged = models.BooleanField(_('flagged'), default=False)
    is_edited = models.BooleanField(_('edited'), default=False)

    # Engagement
    likes_count = models.PositiveIntegerField(_('likes count'), default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CommentManager()

    class Meta:
        verbose_name = _('Comment')
        verbose_name_plural = _('Comments')
        ordering = ['created_at']
        db_table = 'comments_comment'
        indexes = [
            models.Index(fields=['content_type', 'object_id', 'is_active']),
            models.Index(fields=['parent', 'created_at']),
            models.Index(fields=['author', '-created_at']),
        ]

    def __str__(self):
        return f'{self.author.get_full_name()}: {self.content[:50]}...'

    # ------------------------------------------------------------------
    # Validation / persistence
    # ------------------------------------------------------------------
    def compute_depth(self):
        """Depth derived from the parent chain (0 for a root comment)."""
        if self.parent_id is None:
            return 0
        return self.parent.depth + 1

    def clean(self):
        """Custom validation"""
        if self.parent_id is not None:
            parent = self.parent
            if parent.pk == self.pk:
                raise ValidationError(_('A comment cannot be its own parent'))
            if (parent.content_type_id != self.content_type_id
                    or str(parent.object_id) != str(self.object_id)):
                raise ValidationError(_('Parent comment must be on the same object'))
            if self.compute_depth() > MAX_THREAD_DEPTH:
                raise ValidationError(_('Comment thread too deep'))

    def save(self, *args, **kwargs):
        self.depth = self.compute_depth()
        self.clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        target = self.content_object
        if target is not None and hasattr(target, 'get_absolute_url'):
            return f"{target.get_absolute_url()}#comment-{self.id}"
        return reverse('comments:list')

    # ------------------------------------------------------------------
    # Threading helpers
    # ------------------------------------------------------------------
    @property
    def is_root(self):
        """Check if this is a root comment"""
        return self.parent_id is None

    @property
    def can_reply(self):
        """Whether replies to this comment are allowed (depth limit)."""
        return self.is_active and self.get_thread_depth() < MAX_THREAD_DEPTH

    @property
    def reply_count(self):
        """Number of direct active replies (uses annotation when present)."""
        annotated = getattr(self, 'active_reply_count', None)
        if annotated is not None:
            return annotated
        if hasattr(self, 'child_nodes'):
            return len([c for c in self.child_nodes if not c.is_placeholder])
        return self.replies.filter(is_active=True).count()

    @property
    def total_replies(self):
        """
        Total number of active replies in the whole subtree.

        Uses the value computed by ``build_comment_tree`` when available,
        otherwise fetches all comments on the object in a single query.
        """
        cached = getattr(self, '_total_replies', None)
        if cached is not None:
            return cached
        rows = Comment.objects.filter(
            content_type_id=self.content_type_id,
            object_id=self.object_id,
            is_active=True,
        ).values_list('id', 'parent_id')
        children = defaultdict(list)
        for comment_id, parent_id in rows:
            children[parent_id].append(comment_id)
        count = 0
        stack = [self.id]
        while stack:
            for child_id in children.get(stack.pop(), ()):
                count += 1
                stack.append(child_id)
        return count

    def get_thread_depth(self):
        """Get depth level in thread (0 for root comments)."""
        if self._state.adding:
            return self.compute_depth()
        return self.depth

    def get_replies_tree(self):
        """Get nested replies as a tree structure (single query)."""
        if not hasattr(self, 'child_nodes'):
            comments = list(Comment.objects.filter(
                content_type_id=self.content_type_id,
                object_id=self.object_id,
            ).with_author())
            # build_comment_tree attaches child_nodes onto the fetched instances
            build_comment_tree(comments)
            me = next((c for c in comments if c.id == self.id), None)
            self.child_nodes = me.child_nodes if me else []
        return [
            {'comment': reply, 'replies': reply.get_replies_tree()}
            for reply in self.child_nodes
        ]

    # ------------------------------------------------------------------
    # Permissions
    # ------------------------------------------------------------------
    def can_edit(self, user):
        """Staff can always edit; authors only within the edit window."""
        if not getattr(user, 'is_authenticated', False):
            return False
        if user.is_staff or user.is_superuser:
            return True
        if user.pk != self.author_id or not self.is_active:
            return False
        return self.created_at is None or timezone.now() - self.created_at <= EDIT_WINDOW

    def can_delete(self, user):
        """Authors and staff can delete."""
        if not getattr(user, 'is_authenticated', False):
            return False
        return user.pk == self.author_id or user.is_staff or user.is_superuser

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def mark_as_edited(self):
        """Mark comment as edited"""
        self.is_edited = True
        self.save(update_fields=['is_edited', 'updated_at'])

    def flag(self):
        """Mark the comment as flagged for moderation."""
        if not self.is_flagged:
            self.is_flagged = True
            self.save(update_fields=['is_flagged'])

    def add_flag(self, user, reason='other', details=''):
        """
        Record a flag by ``user``. The comment becomes flagged once
        COMMENTS_FLAG_THRESHOLD distinct users have flagged it (staff flags
        count immediately). Returns (flag, created).
        """
        flag, created = CommentFlag.objects.get_or_create(
            comment=self, user=user,
            defaults={'reason': reason, 'details': details},
        )
        if created and not self.is_flagged:
            if user.is_staff or self.flags.count() >= get_flag_threshold():
                self.flag()
        return flag, created

    def toggle_like(self, user):
        """
        Atomically like/unlike the comment for ``user``.

        Returns (liked, likes_count). The counter itself is maintained with
        F() expressions in the CommentLike signal handlers.
        """
        with transaction.atomic():
            like, created = CommentLike.objects.get_or_create(comment=self, user=user)
            if not created:
                like.delete()
        self.refresh_from_db(fields=['likes_count'])
        return created, self.likes_count

    def soft_delete(self):
        """Soft delete comment"""
        self.is_active = False
        self.content = '[Comment deleted]'
        self.save(update_fields=['is_active', 'content', 'updated_at'])

    def restore(self):
        """Re-activate a hidden comment (moderation)."""
        self.is_active = True
        self.is_flagged = False
        self.save(update_fields=['is_active', 'is_flagged', 'updated_at'])


class CommentLike(models.Model):
    """Like model for comments"""

    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comment_likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Comment Like')
        verbose_name_plural = _('Comment Likes')
        unique_together = ['comment', 'user']
        db_table = 'comments_commentlike'

    def __str__(self):
        return f'{self.user.get_full_name()} likes {self.comment}'


class CommentFlag(models.Model):
    """A report filed by a user against a comment."""

    class Reason(models.TextChoices):
        SPAM = 'spam', _('Spam')
        OFFENSIVE = 'offensive', _('Offensive language')
        HARASSMENT = 'harassment', _('Harassment')
        OFF_TOPIC = 'off_topic', _('Off topic')
        COPYRIGHT = 'copyright', _('Copyright violation')
        OTHER = 'other', _('Other')

    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='flags')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_flags')
    reason = models.CharField(_('reason'), max_length=20, choices=Reason.choices, default=Reason.OTHER)
    details = models.CharField(_('details'), max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Comment Flag')
        verbose_name_plural = _('Comment Flags')
        db_table = 'comments_commentflag'
        constraints = [
            models.UniqueConstraint(fields=['comment', 'user'], name='unique_comment_flag_per_user'),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} flagged {self.comment_id} ({self.reason})'
