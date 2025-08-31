# File: DjangoVerseHub/apps/articles/managers.py

from django.db import models
from django.utils import timezone


class ArticleQuerySet(models.QuerySet):
    """Custom queryset for Article model"""
    
    def published(self):
        """Return only published articles"""
        return self.filter(status='published', published_at__lte=timezone.now())
    
    def draft(self):
        """Return only draft articles"""
        return self.filter(status='draft')
    
    def archived(self):
        """Return only archived articles"""
        return self.filter(status='archived')
    
    def featured(self):
        """Return only featured articles"""
        return self.filter(is_featured=True)
    
    def by_category(self, category_slug):
        """Filter articles by category slug"""
        return self.filter(category__slug=category_slug)
    
    def by_tag(self, tag_slug):
        """Filter articles by tag slug"""
        return self.filter(tags__slug=tag_slug)
    
    def by_author(self, author):
        """Filter articles by author"""
        return self.filter(author=author)
    
    def search(self, query):
        """Search articles by title and content"""
        return self.filter(
            models.Q(title__icontains=query) |
            models.Q(content__icontains=query) |
            models.Q(summary__icontains=query)
        )
    
    def popular(self):
        """Return articles ordered by popularity (views + likes)"""
        return self.annotate(
            popularity=models.F('views_count') + models.F('likes_count')
        ).order_by('-popularity')
    
    def trending(self, days=7):
        """Return trending articles from the last N days"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return self.filter(
            created_at__gte=cutoff_date
        ).annotate(
            trend_score=models.F('views_count') + models.F('likes_count') * 2
        ).order_by('-trend_score')
    
    def with_comments_count(self):
        """Annotate with comments count"""
        return self.annotate(
            comments_count=models.Count('comments', filter=models.Q(comments__is_active=True))
        )
    
    def recent(self, limit=10):
        """Return recent articles"""
        return self.order_by('-created_at')[:limit]


class ArticleManager(models.Manager):
    """Custom manager for Article model"""
    
    def get_queryset(self):
        return ArticleQuerySet(self.model, using=self._db)
    
    def published(self):
        return self.get_queryset().published()
    
    def draft(self):
        return self.get_queryset().draft()
    
    def archived(self):
        return self.get_queryset().archived()
    
    def featured(self):
        return self.get_queryset().featured()
    
    def by_category(self, category_slug):
        return self.get_queryset().by_category(category_slug)
    
    def by_tag(self, tag_slug):
        return self.get_queryset().by_tag(tag_slug)
    
    def by_author(self, author):
        return self.get_queryset().by_author(author)
    
    def search(self, query):
        return self.get_queryset().search(query)
    
    def popular(self):
        return self.get_queryset().popular()
    
    def trending(self, days=7):
        return self.get_queryset().trending(days)


class PublishedManager(models.Manager):
    """Manager that returns only published articles"""
    
    def get_queryset(self):
        return ArticleQuerySet(self.model, using=self._db).published()
    
    def featured(self):
        return self.get_queryset().featured()
    
    def by_category(self, category_slug):
        return self.get_queryset().by_category(category_slug)
    
    def by_tag(self, tag_slug):
        return self.get_queryset().by_tag(tag_slug)
    
    def popular(self):
        return self.get_queryset().popular()
    
    def trending(self, days=7):
        return self.get_queryset().trending(days)


class CategoryManager(models.Manager):
    """Custom manager for Category model"""
    
    def active(self):
        """Return only active categories"""
        return self.filter(is_active=True)
    
    def with_article_count(self):
        """Annotate with article count"""
        return self.annotate(
            article_count=models.Count('articles', filter=models.Q(articles__status='published'))
        )
    
    def popular(self):
        """Return categories ordered by article count"""
        return self.with_article_count().order_by('-article_count')


class TagManager(models.Manager):
    """Custom manager for Tag model"""
    
    def with_article_count(self):
        """Annotate with article count"""
        return self.annotate(
            article_count=models.Count('articles', filter=models.Q(articles__status='published'))
        )
    
    def popular(self, limit=20):
        """Return popular tags"""
        return self.with_article_count().order_by('-article_count')[:limit]
    
    def used(self):
        """Return only tags that have articles"""
        return self.filter(articles__isnull=False).distinct()