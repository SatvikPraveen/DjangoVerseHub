# File: DjangoVerseHub/apps/articles/models.py

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django_verse_hub.utils import upload_to_path, generate_unique_slug
from .managers import ArticleManager, PublishedManager

User = get_user_model()


class Category(models.Model):
    """Article category model"""
    
    name = models.CharField(_('name'), max_length=100, unique=True)
    slug = models.SlugField(_('slug'), max_length=100, unique=True)
    description = models.TextField(_('description'), blank=True)
    image = models.ImageField(
        _('image'), 
        upload_to=upload_to_path, 
        blank=True, 
        null=True
    )
    is_active = models.BooleanField(_('active'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')
        ordering = ['name']
        db_table = 'articles_category'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('articles:category', kwargs={'slug': self.slug})

    @property
    def article_count(self):
        return self.articles.filter(status='published').count()


class Tag(models.Model):
    """Article tag model"""
    
    name = models.CharField(_('name'), max_length=50, unique=True)
    slug = models.SlugField(_('slug'), max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Tag')
        verbose_name_plural = _('Tags')
        ordering = ['name']
        db_table = 'articles_tag'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('articles:tag', kwargs={'slug': self.slug})

    @property
    def article_count(self):
        return self.articles.filter(status='published').count()


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
        User,
        on_delete=models.CASCADE,
        related_name='articles',
        verbose_name=_('author')
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name='articles',
        null=True,
        blank=True,
        verbose_name=_('category')
    )
    tags = models.ManyToManyField(
        Tag,
        related_name='articles',
        blank=True,
        verbose_name=_('tags')
    )
    
    # Content
    summary = models.TextField(_('summary'), max_length=500, blank=True)
    content = models.TextField(_('content'))
    featured_image = models.ImageField(
        _('featured image'),
        upload_to=upload_to_path,
        blank=True,
        null=True
    )
    
    # Status and publication
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    published_at = models.DateTimeField(_('published at'), null=True, blank=True)
    is_featured = models.BooleanField(_('featured'), default=False)
    allow_comments = models.BooleanField(_('allow comments'), default=True)
    
    # SEO
    meta_description = models.CharField(
        _('meta description'), 
        max_length=160, 
        blank=True,
        help_text=_('SEO meta description')
    )
    meta_keywords = models.CharField(
        _('meta keywords'), 
        max_length=200, 
        blank=True,
        help_text=_('Comma-separated keywords')
    )
    
    # Statistics
    views_count = models.PositiveIntegerField(_('views count'), default=0)
    likes_count = models.PositiveIntegerField(_('likes count'), default=0)
    shares_count = models.PositiveIntegerField(_('shares count'), default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = generate_unique_slug(self, 'title')
        
        # Set published_at when status changes to published
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        elif self.status != 'published':
            self.published_at = None
            
        # Generate meta description from content if not provided
        if not self.meta_description and self.content:
            self.meta_description = self.content[:150] + '...' if len(self.content) > 150 else self.content
            
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('articles:detail', kwargs={'slug': self.slug})

    @property
    def is_published(self):
        return self.status == 'published'

    @property
    def comment_count(self):
        return self.comments.filter(is_active=True).count()

    @property
    def reading_time(self):
        """Estimate reading time in minutes"""
        word_count = len(self.content.split())
        return max(1, word_count // 200)  # Assuming 200 words per minute

    def get_featured_image_url(self):
        if self.featured_image:
            return self.featured_image.url
        return '/static/images/default-article.png'

    def increment_views(self):
        """Increment view count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])

    def get_related_articles(self, limit=5):
        """Get related articles based on tags and category"""
        related = Article.published.filter(
            models.Q(tags__in=self.tags.all()) |
            models.Q(category=self.category)
        ).exclude(id=self.id).distinct()
        return related[:limit]