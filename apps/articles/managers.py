# File: DjangoVerseHub/apps/articles/managers.py

from django.db import models
from django.utils import timezone


class ArticleQuerySet(models.QuerySet):
    """Custom queryset for Article model"""

    def published(self):
        """Return only published articles"""
        return self.filter(status="published", published_at__lte=timezone.now())

    def draft(self):
        """Return only draft articles"""
        return self.filter(status="draft")

    def archived(self):
        """Return only archived articles"""
        return self.filter(status="archived")

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

    def visible_to(self, user):
        """Published articles, plus the user's own drafts (or everything for staff)."""
        if user is not None and user.is_authenticated:
            if user.is_staff:
                return self
            return self.filter(models.Q(status="published") | models.Q(author=user))
        return self.filter(status="published")

    def search(self, query):
        """Search articles by title and content"""
        return self.filter(
            models.Q(title__icontains=query) | models.Q(content__icontains=query) | models.Q(summary__icontains=query)
        )

    def popular(self):
        """Return articles ordered by popularity (views + likes)"""
        return self.annotate(popularity=models.F("views_count") + models.F("likes_count")).order_by("-popularity")

    def trending(self, days=7):
        """Return trending articles from the last N days"""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        return (
            self.filter(created_at__gte=cutoff_date)
            .annotate(trend_score=models.F("views_count") + models.F("likes_count") * 2)
            .order_by("-trend_score", "-created_at")
        )

    def with_related(self):
        """Eager-load everything the list templates/serializers touch."""
        from .models import Tag  # local import to avoid a circular import

        return self.select_related("author", "author__profile", "category").prefetch_related(
            models.Prefetch("tags", queryset=Tag.objects.with_article_count())
        )

    def with_user_flags(self, user):
        """Annotate ``is_liked`` / ``is_bookmarked`` for ``user`` in a single query."""
        from .models import ArticleLike, Bookmark  # local import to avoid a circular import

        if user is None or not user.is_authenticated:
            return self.annotate(
                is_liked=models.Value(False, output_field=models.BooleanField()),
                is_bookmarked=models.Value(False, output_field=models.BooleanField()),
            )
        return self.annotate(
            is_liked=models.Exists(ArticleLike.objects.filter(article=models.OuterRef("pk"), user=user)),
            is_bookmarked=models.Exists(Bookmark.objects.filter(article=models.OuterRef("pk"), user=user)),
        )

    def recent(self, limit=10):
        """Return recent articles"""
        return self.order_by("-created_at")[:limit]


class ArticleManager(models.Manager.from_queryset(ArticleQuerySet)):
    """Custom manager for Article model (all statuses)."""


class PublishedManager(models.Manager.from_queryset(ArticleQuerySet)):
    """Manager that returns only published articles"""

    def get_queryset(self):
        return super().get_queryset().published()


class CategoryQuerySet(models.QuerySet):
    """Chainable helpers for Category."""

    def active(self):
        """Return only active categories"""
        return self.filter(is_active=True)

    def with_article_count(self):
        """Annotate with published article count (read through Category.article_count)."""
        return self.annotate(article_count=models.Count("articles", filter=models.Q(articles__status="published")))

    def popular(self):
        """Return categories ordered by article count"""
        return self.with_article_count().order_by("-article_count", "name")


class CategoryManager(models.Manager.from_queryset(CategoryQuerySet)):
    """Custom manager for Category model"""


class TagQuerySet(models.QuerySet):
    """Chainable helpers for Tag."""

    def with_article_count(self):
        """Annotate with published article count (read through Tag.article_count)."""
        return self.annotate(article_count=models.Count("articles", filter=models.Q(articles__status="published")))

    def popular(self, limit=20):
        """Return popular tags"""
        return self.with_article_count().order_by("-article_count", "name")[:limit]

    def used(self):
        """Return only tags that have articles"""
        return self.filter(articles__isnull=False).distinct()


class TagManager(models.Manager.from_queryset(TagQuerySet)):
    """Custom manager for Tag model"""
