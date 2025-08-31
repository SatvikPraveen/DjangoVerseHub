# File: DjangoVerseHub/apps/comments/models.py

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

User = get_user_model()


class CommentManager(models.Manager):
    """Custom manager for Comment model"""
    
    def active(self):
        """Return only active comments"""
        return self.filter(is_active=True)
    
    def for_object(self, obj):
        """Get comments for a specific object"""
        content_type = ContentType.objects.get_for_model(obj)
        return self.filter(
            content_type=content_type,
            object_id=obj.pk,
            is_active=True
        )
    
    def root_comments(self):
        """Get only root level comments (no parent)"""
        return self.filter(parent=None)
    
    def thread_comments(self, parent_comment):
        """Get all comments in a thread"""
        return self.filter(parent=parent_comment)


class Comment(models.Model):
    """Threaded comment model for any content type"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Generic foreign key to allow comments on any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
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

    def clean(self):
        """Custom validation"""
        if self.parent and self.parent.content_type != self.content_type:
            raise ValidationError(_('Parent comment must be on the same object'))
        
        if self.parent and self.parent.object_id != self.object_id:
            raise ValidationError(_('Parent comment must be on the same object'))
        
        # Prevent deeply nested threads (max 3 levels)
        if self.parent and self.get_thread_depth() > 3:
            raise ValidationError(_('Comment thread too deep'))

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return f"{self.content_object.get_absolute_url()}#comment-{self.id}"

    @property
    def is_root(self):
        """Check if this is a root comment"""
        return self.parent is None

    @property
    def reply_count(self):
        """Get number of direct replies"""
        return self.replies.filter(is_active=True).count()

    @property
    def total_replies(self):
        """Get total number of replies in thread"""
        count = 0
        for reply in self.replies.filter(is_active=True):
            count += 1 + reply.total_replies
        return count

    def get_thread_depth(self):
        """Get depth level in thread"""
        depth = 0
        current = self.parent
        while current:
            depth += 1
            current = current.parent
        return depth

    def get_replies_tree(self):
        """Get nested replies as a tree structure"""
        replies = []
        for reply in self.replies.filter(is_active=True).order_by('created_at'):
            reply_data = {
                'comment': reply,
                'replies': reply.get_replies_tree()
            }
            replies.append(reply_data)
        return replies

    def can_edit(self, user):
        """Check if user can edit this comment"""
        if user == self.author:
            # Allow editing within 15 minutes of creation
            from django.utils import timezone
            from datetime import timedelta
            edit_window = timezone.now() - timedelta(minutes=15)
            return self.created_at > edit_window
        return user.is_staff or user.is_superuser

    def can_delete(self, user):
        """Check if user can delete this comment"""
        return user == self.author or user.is_staff or user.is_superuser

    def mark_as_edited(self):
        """Mark comment as edited"""
        self.is_edited = True
        self.save(update_fields=['is_edited', 'updated_at'])

    def flag(self):
        """Flag comment for moderation"""
        self.is_flagged = True
        self.save(update_fields=['is_flagged'])

    def soft_delete(self):
        """Soft delete comment"""
        self.is_active = False
        self.content = '[Comment deleted]'
        self.save(update_fields=['is_active', 'content'])


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