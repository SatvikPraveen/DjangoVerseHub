# File: DjangoVerseHub/apps/articles/feeds.py
"""RSS 2.0 and Atom feeds for published articles, per category, tag and author."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.syndication.views import Feed
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.feedgenerator import Atom1Feed

from apps.core.markdown import markdown_to_text, render_markdown

from .models import Article, Category, Tag

User = get_user_model()


class LatestArticlesFeed(Feed):
    title = f"{getattr(settings, 'SITE_NAME', 'DjangoVerseHub')} - Latest articles"
    description = "The newest articles published on DjangoVerseHub."
    limit = 25

    def link(self):
        return reverse("articles:list")

    def items(self):
        return self.queryset().select_related("author", "category").prefetch_related("tags")[: self.limit]

    def queryset(self):
        return Article.published.order_by("-published_at")

    # -- item fields ---------------------------------------------------------
    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return render_markdown(item.summary or item.content[:2000])

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at or item.created_at

    def item_updateddate(self, item):
        return item.updated_at

    def item_author_name(self, item):
        return item.author.get_full_name() or item.author.username

    def item_author_link(self, item):
        return item.author.get_absolute_url()

    def item_categories(self, item):
        names = [tag.name for tag in item.tags.all()]
        if item.category_id:
            names.insert(0, item.category.name)
        return names

    def item_guid(self, item):
        return str(item.pk)


class LatestArticlesAtomFeed(LatestArticlesFeed):
    feed_type = Atom1Feed
    subtitle = LatestArticlesFeed.description


class CategoryFeed(LatestArticlesFeed):
    def get_object(self, request, slug):
        return get_object_or_404(Category, slug=slug, is_active=True)

    def title(self, obj):
        return f"{obj.name} - DjangoVerseHub"

    def description(self, obj):
        return obj.description or f"Articles in {obj.name}."

    def link(self, obj):
        return obj.get_absolute_url()

    def items(self, obj):
        return (
            Article.published.filter(category=obj)
            .select_related("author", "category")
            .prefetch_related("tags")
            .order_by("-published_at")[: self.limit]
        )


class TagFeed(LatestArticlesFeed):
    def get_object(self, request, slug):
        return get_object_or_404(Tag, slug=slug)

    def title(self, obj):
        return f"#{obj.name} - DjangoVerseHub"

    def description(self, obj):
        return f"Articles tagged {obj.name}."

    def link(self, obj):
        return obj.get_absolute_url()

    def items(self, obj):
        return (
            Article.published.filter(tags=obj)
            .select_related("author", "category")
            .prefetch_related("tags")
            .order_by("-published_at")[: self.limit]
        )


class AuthorFeed(LatestArticlesFeed):
    def get_object(self, request, username):
        return get_object_or_404(User, username=username, is_active=True)

    def title(self, obj):
        return f"{obj.get_full_name() or obj.username} - DjangoVerseHub"

    def description(self, obj):
        return (
            markdown_to_text(getattr(getattr(obj, "profile", None), "bio", ""), 200) or f"Articles by {obj.username}."
        )

    def link(self, obj):
        return obj.get_absolute_url()

    def items(self, obj):
        return (
            Article.published.filter(author=obj)
            .select_related("author", "category")
            .prefetch_related("tags")
            .order_by("-published_at")[: self.limit]
        )
