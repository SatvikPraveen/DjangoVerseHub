# File: DjangoVerseHub/apps/articles/models.py

import math
import re
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.core.cache import cache
from django.db import models, transaction
from django.db.models.functions import Greatest
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.comments.models import Comment
from django_verse_hub.utils import get_client_ip, upload_to_path

from .managers import ArticleManager, CategoryManager, PublishedManager, TagManager

# Fields whose changes are captured as an ArticleRevision.
REVISION_FIELDS = ('title', 'content', 'summary')

# A view from the same session/IP is only counted once per this many seconds.
VIEW_DEDUPE_SECONDS = 60 * 60


def _unique_slug(instance, source_field, max_length=200):
    """Build a slug from ``source_field`` that is unique for the model, ignoring ``instance`` itself."""
    base = slugify(getattr(instance, source_field))[:max_length] or 'item'
    manager = instance.__class__._default_manager
    candidate = base
    counter = 1
    while manager.filter(slug=candidate).exclude(pk=instance.pk).exists():
        suffix = f'-{counter}'
        candidate = f'{base[:max_length - len(suffix)]}{suffix}'
        counter += 1
    return candidate


class AnnotatedArticleCountMixin:
    """``article_count`` reads a queryset annotation when present, otherwise runs a query.

    ``CategoryManager.with_article_count()`` / ``TagManager.with_article_count()`` (and
    other callers) annotate the queryset with ``article_count``; Django assigns the
    annotation with ``setattr``, so the property needs a setter.
    """

    @property
    def article_count(self):
        cached = self.__dict__.get('_article_count')
        if cached is not None:
            return cached
        return self.articles.filter(status='published').count()

    @article_count.setter
    def article_count(self, value):
        self.__dict__['_article_count'] = value


class Category(AnnotatedArticleCountMixin, models.Model):
    """Article category model"""

    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), max_length=100, unique=True, blank=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(_('image'), upload_to=upload_to_path, blank=True, null=True)
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CategoryManager()

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name']
        db_table = 'articles_category'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, 'name', max_length=100)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('articles:category_detail', kwargs={'slug': self.slug})


class Tag(AnnotatedArticleCountMixin, models.Model):
    """Article tag model"""

    name = models.CharField(_('name'), max_length=50, unique=True)
    slug = models.SlugField(_('slug'), max_length=50, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TagManager()

    class Meta:
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')
        ordering = ['name']
        db_table = 'articles_tag'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _unique_slug(self, 'name', max_length=50)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('articles:tag_detail', kwargs={'slug': self.slug})


class Article(models.Model):
    """Main article model"""

    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('published', _('Published')),
        ('archived', _('Archived')),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(_('title'), max_length=200)
    slug = models.SlugField(_('slug'), max_length=200, unique=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='articles',
        verbose_name=_('author'),
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='articles',
        null=True,
        blank=True,
        verbose_name=_('category'),
    )
    tags = models.ManyToManyField(Tag, related_name='articles', blank=True, verbose_name=_('tags'))

    # Content
    summary = models.TextField(_('summary'), max_length=500, blank=True)
    content = models.TextField(_('content'))
    featured_image = models.ImageField(_('featured image'), upload_to=upload_to_path, blank=True, null=True)

    # Status and publication
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    allow_comments = models.BooleanField(_('allow comments'), default=True)

    # SEO
    meta_description = models.CharField(
        _('meta description'), max_length=160, blank=True, help_text=_('SEO meta description')
    )
    meta_keywords = models.CharField(
        _('meta keywords'), max_length=200, blank=True, help_text=_('Comma-separated keywords')
    )

    # Statistics (denormalised counters; likes_count is driven by ArticleLike)
    views_count = models.PositiveIntegerField(_('views count'), default=0)
    likes_count = models.PositiveIntegerField(_('likes count'), default=0)
    shares_count = models.PositiveIntegerField(_('shares count'), default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Comments live in apps.comments and attach through a generic FK.
    # Comment.object_id is a UUIDField matching our pk, so both instance access
    # (article.comments.all(), cascade delete) and SQL joins/annotations work.
    comments = GenericRelation(
        Comment,
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='article',
    )

    # Managers
    objects = ArticleManager()
    published = PublishedManager()

    class Meta:
        verbose_name = _('Article')
        verbose_name_plural = _('Articles')
        ordering = ['-created_at']
        db_table = 'articles_article'
        indexes = [
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['author', '-created_at']),
            models.Index(fields=['category', '-published_at']),
            models.Index(fields=['-views_count']),
            models.Index(fields=['-likes_count']),
        ]

    def __str__(self):
        return self.title

    # ------------------------------------------------------------------ persistence
    def save(self, *args, editor=None, **kwargs):
        """Save the article.

        ``editor`` (optional user) is recorded on the ArticleRevision that is created
        when the title, content or summary of an existing article changes.
        """
        if not self.slug:
            self.slug = _unique_slug(self, 'title', max_length=200)

        # Set published_at when status changes to published; clear it otherwise
        self._just_published = False
        if self.status == 'published':
            if not self.published_at:
                self.published_at = timezone.now()
                self._just_published = True
        else:
            self.published_at = None

        # Generate meta description from content if not provided
        if not self.meta_description and self.content:
            text = strip_tags(self.content).strip()
            self.meta_description = text[:157].rstrip() + '...' if len(text) > 160 else text[:160]

        previous = self._get_previous_revision_values(kwargs.get('update_fields'))

        with transaction.atomic():
            super().save(*args, **kwargs)
            if previous is not None:
                ArticleRevision.objects.create(article=self, editor=editor, **previous)

    def _get_previous_revision_values(self, update_fields):
        """Return the stored title/content/summary if this save changes any of them, else None."""
        if self._state.adding or not self.pk:
            return None
        if update_fields is not None and not set(update_fields) & set(REVISION_FIELDS):
            return None
        previous = Article.objects.filter(pk=self.pk).values(*REVISION_FIELDS).first()
        if previous is None:
            return None
        if all(previous[field] == getattr(self, field) for field in REVISION_FIELDS):
            return None
        return previous

    def get_absolute_url(self):
        return reverse('articles:detail', kwargs={'slug': self.slug})

    # ------------------------------------------------------------------ derived data
    @property
    def is_published(self):
        return self.status == 'published'

    @property
    def comment_count(self):
        cached = self.__dict__.get('_comment_count')
        if cached is not None:
            return cached
        return self.comments.filter(is_active=True).count()

    @comment_count.setter
    def comment_count(self, value):
        self.__dict__['_comment_count'] = value

    @classmethod
    def attach_comment_counts(cls, articles):
        """Populate ``comment_count`` on a list of articles with a single query.

        Cheaper than a join-based annotation on large lists, and keeps the
        is_active filter explicit.
        """
        articles = list(articles)
        if not articles:
            return articles
        from django.contrib.contenttypes.models import ContentType

        counts = dict(
            Comment.objects.filter(
                content_type=ContentType.objects.get_for_model(cls),
                object_id__in=[article.pk for article in articles],
                is_active=True,
            )
            .values_list('object_id')
            .annotate(total=models.Count('id'))
            .values_list('object_id', 'total')
        )
        for article in articles:
            article.comment_count = counts.get(article.pk, 0)
        return articles

    @property
    def reading_time(self):
        """Estimated reading time in whole minutes (at least 1), based on ~200 words per minute."""
        words = len(re.findall(r'\S+', strip_tags(self.content or '')))
        return max(1, math.ceil(words / 200))

    def get_featured_image_url(self):
        if self.featured_image:
            return self.featured_image.url
        return '/static/images/default-article.png'

    def can_be_viewed_by(self, user):
        """Published articles are public; drafts/archived are visible to the author and staff."""
        if self.is_published:
            return True
        return bool(user and user.is_authenticated and (user.pk == self.author_id or user.is_staff))

    def can_be_edited_by(self, user):
        return bool(user and user.is_authenticated and (user.pk == self.author_id or user.is_staff))

    def is_liked_by(self, user):
        if not (user and user.is_authenticated):
            return False
        annotated = self.__dict__.get('is_liked')
        if annotated is not None:
            return annotated
        return self.likes.filter(user=user).exists()

    def is_bookmarked_by(self, user):
        if not (user and user.is_authenticated):
            return False
        annotated = self.__dict__.get('is_bookmarked')
        if annotated is not None:
            return annotated
        return self.bookmarks.filter(user=user).exists()

    # ------------------------------------------------------------------ engagement
    def increment_views(self, request=None):
        """Atomically bump the view counter.

        When ``request`` is given, repeat views from the same session (or IP for
        anonymous users without a session) within VIEW_DEDUPE_SECONDS are ignored.
        Returns True when a view was counted.
        """
        if request is not None:
            session = getattr(request, 'session', None)
            visitor = getattr(session, 'session_key', None) or get_client_ip(request)
            if visitor:
                cache_key = f'article:{self.pk}:viewed:{visitor}'
                if not cache.add(cache_key, 1, VIEW_DEDUPE_SECONDS):
                    return False

        Article.objects.filter(pk=self.pk).update(views_count=models.F('views_count') + 1)
        self.views_count = Article.objects.filter(pk=self.pk).values_list('views_count', flat=True).get()
        return True

    def get_related_articles(self, limit=5):
        """Published articles sharing tags (most shared first), topped up by same-category articles."""
        tag_ids = list(self.tags.values_list('id', flat=True))
        base = Article.published.exclude(pk=self.pk).select_related('author', 'category')
        related = []

        if tag_ids:
            related = list(
                base.filter(tags__in=tag_ids)
                .annotate(shared_tags=models.Count('tags', filter=models.Q(tags__in=tag_ids)))
                .order_by('-shared_tags', '-published_at')[:limit]
            )

        if len(related) < limit and self.category_id:
            seen = {article.pk for article in related}
            for article in base.filter(category_id=self.category_id).order_by('-published_at'):
                if article.pk not in seen:
                    related.append(article)
                    if len(related) >= limit:
                        break

        return related


class Bookmark(models.Model):
    """A user saving an article to read later."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookmarks')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Bookmark')
        verbose_name_plural = _('Bookmarks')
        db_table = 'articles_bookmark'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'article'], name='unique_article_bookmark'),
        ]

    def __str__(self):
        return f'{self.user} bookmarked {self.article}'

    @classmethod
    def toggle(cls, user, article):
        """Add or remove the bookmark. Returns True when the article is now bookmarked."""
        bookmark, created = cls.objects.get_or_create(user=user, article=article)
        if created:
            return True
        bookmark.delete()
        return False


class ArticleLike(models.Model):
    """A user liking an article; keeps Article.likes_count in sync."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='article_likes')
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Article like')
        verbose_name_plural = _('Article likes')
        db_table = 'articles_articlelike'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'article'], name='unique_article_like'),
        ]

    def __str__(self):
        return f'{self.user} likes {self.article}'

    @classmethod
    def toggle(cls, user, article):
        """Like or unlike the article atomically. Returns (liked, likes_count)."""
        with transaction.atomic():
            like, created = cls.objects.get_or_create(user=user, article=article)
            if created:
                delta = 1
            else:
                like.delete()
                delta = -1
            Article.objects.filter(pk=article.pk).update(
                likes_count=Greatest(models.F('likes_count') + delta, 0)
            )
        article.likes_count = Article.objects.filter(pk=article.pk).values_list('likes_count', flat=True).get()
        return created, article.likes_count


class ArticleRevision(models.Model):
    """Snapshot of an article's title/content/summary taken right before it was changed.

    ``editor`` is the user whose edit superseded this version (null for system saves).
    """

    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='revisions')
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='article_revisions',
        null=True,
        blank=True,
    )
    title = models.CharField(_('title'), max_length=200)
    content = models.TextField(_('content'))
    summary = models.TextField(_('summary'), max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Article revision')
        verbose_name_plural = _('Article revisions')
        db_table = 'articles_articlerevision'
        ordering = ['-created_at', '-id']
        indexes = [models.Index(fields=['article', '-created_at'])]

    def __str__(self):
        return f'Revision of "{self.title}" ({self.created_at:%Y-%m-%d %H:%M})'

    def restore(self, editor=None):
        """Copy this snapshot back onto the article (the current text becomes a new revision)."""
        article = self.article
        article.title = self.title
        article.content = self.content
        article.summary = self.summary
        article.save(editor=editor, update_fields=list(REVISION_FIELDS) + ['updated_at'])
        return article
