# File: DjangoVerseHub/apps/articles/views.py

from django_filters.rest_framework import DjangoFilterBackend

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.http import HttpResponseNotModified, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.comments.models import Comment
from django_verse_hub.permissions import IsOwnerOrReadOnly, IsStaffOrReadOnly

from .cache import ArticleCacheManager
from .forms import ArticleForm, ArticleSearchForm
from .models import Article, ArticleLike, ArticleRevision, Bookmark, Category, Tag
from .search import ArticleSearchManager, search_all
from .serializers import (
    ArticleCreateUpdateSerializer,
    ArticleDetailSerializer,
    ArticleListSerializer,
    ArticleRevisionSerializer,
    CategoryCreateUpdateSerializer,
    CategorySerializer,
    PopularArticleSerializer,
    TagCreateUpdateSerializer,
    TagSerializer,
)

LIST_ORDERINGS = ("-created_at", "created_at", "-published_at", "-views_count", "-likes_count", "title", "-title")


def _is_ajax(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    return request.accepts("application/json") and not request.accepts("text/html")


class ArticleSidebarMixin:
    """Shared sidebar context for article listings."""

    show_featured = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("search_form", ArticleSearchForm(self.request.GET or None))
        context["categories"] = Category.objects.active().with_article_count()[:10]
        context["popular_tags"] = Tag.objects.popular(20)
        context["featured_articles"] = (
            ArticleCacheManager.get_cached_featured_articles()[:3] if self.show_featured else []
        )
        return context


# ──────────────────────────────────────────────────────────────────────────────
# Article listings
# ──────────────────────────────────────────────────────────────────────────────


class ArticleListView(ArticleSidebarMixin, ListView):
    """List all published articles"""

    model = Article
    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 12

    def get_queryset(self):
        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            queryset = search_all(search_query)
        else:
            queryset = Article.published.with_related()

        category_slug = self.request.GET.get("category")
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)

        tag_slug = self.request.GET.get("tag")
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)

        ordering = self.request.GET.get("ordering")
        if ordering in LIST_ORDERINGS:
            queryset = queryset.order_by(ordering)
        elif not search_query:
            queryset = queryset.order_by("-published_at", "-created_at")

        return queryset.with_user_flags(self.request.user)


class MyArticlesView(LoginRequiredMixin, ArticleSidebarMixin, ListView):
    """Articles written by the current user, in any status."""

    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 12
    page_heading = "My Articles"
    status_filter = None
    show_featured = False

    def get_queryset(self):
        queryset = Article.objects.filter(author=self.request.user).with_related()
        if self.status_filter:
            queryset = queryset.filter(status=self.status_filter)
        return queryset.with_user_flags(self.request.user).order_by("-updated_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_heading"] = self.page_heading
        return context


class DraftsView(MyArticlesView):
    """Unpublished drafts of the current user."""

    page_heading = "My Drafts"
    status_filter = "draft"


class BookmarksView(LoginRequiredMixin, ArticleSidebarMixin, ListView):
    """Articles the current user has bookmarked."""

    template_name = "articles/article_list.html"
    context_object_name = "articles"
    paginate_by = 12
    show_featured = False

    def get_queryset(self):
        return (
            Article.published.filter(bookmarks__user=self.request.user)
            .with_related()
            .with_user_flags(self.request.user)
            .order_by("-bookmarks__created_at")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_heading"] = "Bookmarks"
        return context


# ──────────────────────────────────────────────────────────────────────────────
# Article detail / CRUD
# ──────────────────────────────────────────────────────────────────────────────


class ArticleDetailView(DetailView):
    """Display a single article. Drafts are only visible to their author and staff."""

    model = Article
    template_name = "articles/article_detail.html"
    context_object_name = "article"

    def get_queryset(self):
        return Article.objects.visible_to(self.request.user).with_related().with_user_flags(self.request.user)

    def get(self, request, *args, **kwargs):
        # Anonymous readers see identical markup, so let them revalidate with an ETag.
        etag = None
        if not request.user.is_authenticated:
            etag = self.compute_etag(kwargs.get("slug"))
            if etag and request.headers.get("If-None-Match") == etag:
                return HttpResponseNotModified()
        response = super().get(request, *args, **kwargs)
        if etag:
            response["ETag"] = etag
            response["Cache-Control"] = "private, no-cache"
        return response

    @staticmethod
    def compute_etag(slug):
        """Weak validator from the article's and its latest comment's update time."""
        row = Article.published.filter(slug=slug).values_list("pk", "updated_at").first()
        if row is None:
            return None
        pk, updated_at = row
        latest_comment = (
            Comment.objects.filter(content_type=ContentType.objects.get_for_model(Article), object_id=pk)
            .order_by("-updated_at")
            .values_list("updated_at", flat=True)
            .first()
        )
        stamp = max(filter(None, [updated_at, latest_comment])).timestamp()
        return f'W/"{pk.hex[:12]}-{int(stamp * 1_000_000)}"'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_published:
            obj.increment_views(self.request)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        user = self.request.user
        context["related_articles"] = article.get_related_articles()
        context["comments"] = (
            Comment.objects.for_object(article)
            .filter(parent=None)
            .select_related("author", "author__profile")
            .order_by("created_at")[:10]
        )
        context["article_content_type_id"] = ContentType.objects.get_for_model(Article).pk
        context["is_liked"] = article.is_liked_by(user)
        context["is_bookmarked"] = article.is_bookmarked_by(user)
        context["can_edit"] = article.can_be_edited_by(user)
        return context


class ArticleCreateView(LoginRequiredMixin, CreateView):
    """Create new article"""

    model = Article
    form_class = ArticleForm
    template_name = "articles/article_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.author = self.request.user
        if self.request.POST.get("action") == "publish":
            form.instance.status = "published"
        messages.success(self.request, "Article created successfully!")
        return super().form_valid(form)


class ArticleAuthorRequiredMixin(LoginRequiredMixin):
    """Restrict a slug-based article view to the article's author (or staff)."""

    def get_queryset(self):
        queryset = Article.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(author=self.request.user)
        return queryset


class ArticleUpdateView(ArticleAuthorRequiredMixin, UpdateView):
    """Update existing article"""

    model = Article
    form_class = ArticleForm
    template_name = "articles/article_edit.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Article updated successfully!")
        return super().form_valid(form)


class ArticleDeleteView(ArticleAuthorRequiredMixin, DeleteView):
    """Delete an article (author or staff only)"""

    model = Article
    template_name = "articles/article_confirm_delete.html"
    success_url = reverse_lazy("articles:list")

    def form_valid(self, form):
        messages.success(self.request, "Article deleted successfully!")
        return super().form_valid(form)


class ArticleRevisionListView(ArticleAuthorRequiredMixin, DetailView):
    """Revision history of an article (author or staff only)."""

    model = Article
    template_name = "articles/article_revisions.html"
    context_object_name = "article"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["revisions"] = self.object.revisions.select_related("editor")
        return context


@login_required
@require_POST
def article_revision_restore_view(request, slug, pk):
    """Restore a previous revision of an article (author or staff only)."""
    queryset = Article.objects.all() if request.user.is_staff else Article.objects.filter(author=request.user)
    article = get_object_or_404(queryset, slug=slug)
    revision = get_object_or_404(ArticleRevision, pk=pk, article=article)
    revision.restore(editor=request.user)
    messages.success(request, f"Restored the revision from {revision.created_at:%b %d, %Y %H:%M}.")
    return redirect("articles:revisions", slug=article.slug)


# ──────────────────────────────────────────────────────────────────────────────
# Engagement toggles
# ──────────────────────────────────────────────────────────────────────────────


def _toggle_response(request, article, payload):
    if _is_ajax(request):
        return JsonResponse(payload)
    return redirect(request.POST.get("next") or article.get_absolute_url())


@login_required
@require_POST
def article_like_view(request, slug):
    """Toggle the current user's like on a published article."""
    article = get_object_or_404(Article.published, slug=slug)
    liked, likes_count = ArticleLike.toggle(request.user, article)
    return _toggle_response(request, article, {"liked": liked, "likes_count": likes_count})


@login_required
@require_POST
def article_bookmark_view(request, slug):
    """Toggle the current user's bookmark on a published article."""
    article = get_object_or_404(Article.published, slug=slug)
    bookmarked = Bookmark.toggle(request.user, article)
    return _toggle_response(request, article, {"bookmarked": bookmarked})


# ──────────────────────────────────────────────────────────────────────────────
# API ViewSets
# ──────────────────────────────────────────────────────────────────────────────


class ArticleViewSet(viewsets.ModelViewSet):
    """API ViewSet for Article operations"""

    queryset = Article.objects.all()
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]  # type: ignore[assignment]
    filterset_fields = ["status", "category", "tags", "is_featured"]
    search_fields = ["title", "content", "summary"]
    ordering_fields = ["created_at", "published_at", "views_count", "likes_count"]
    ordering = ["-created_at"]

    def get_queryset(self):
        # Published articles for everyone, plus the caller's own drafts; staff see everything.
        user = self.request.user
        return super().get_queryset().visible_to(user).with_related().with_user_flags(user)

    def get_serializer_class(self):
        if self.action == "list":
            return ArticleListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ArticleCreateUpdateSerializer
        return ArticleDetailSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def _published_list_response(self, queryset, serializer_class=ArticleListSerializer, limit=10):
        queryset = queryset.with_related().with_user_flags(self.request.user)[:limit]
        serializer = serializer_class(queryset, many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.AllowAny])
    def increment_views(self, request, pk=None):
        """Increment article view count (deduplicated per session/IP for an hour)."""
        article = self.get_object()
        article.increment_views(request)
        return Response({"views_count": article.views_count})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def like(self, request, pk=None):
        """Toggle the current user's like."""
        article = self.get_object()
        if not article.is_published:
            return Response({"detail": "Only published articles can be liked."}, status=status.HTTP_400_BAD_REQUEST)
        liked, likes_count = ArticleLike.toggle(request.user, article)
        return Response({"liked": liked, "likes_count": likes_count})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def bookmark(self, request, pk=None):
        """Toggle the current user's bookmark."""
        article = self.get_object()
        if not article.is_published:
            return Response(
                {"detail": "Only published articles can be bookmarked."}, status=status.HTTP_400_BAD_REQUEST
            )
        bookmarked = Bookmark.toggle(request.user, article)
        return Response({"bookmarked": bookmarked})

    @action(detail=True, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def revisions(self, request, pk=None):
        """Revision history (author or staff only)."""
        article = self.get_object()
        if not article.can_be_edited_by(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        serializer = ArticleRevisionSerializer(article.revisions.select_related("editor"), many=True)
        return Response(serializer.data)

    @action(detail=False)
    def featured(self, request):
        """Get featured articles"""
        return self._published_list_response(Article.published.featured())

    @action(detail=False)
    def popular(self, request):
        """Get popular articles"""
        return self._published_list_response(Article.published.popular(), PopularArticleSerializer)

    @action(detail=False)
    def trending(self, request):
        """Get trending articles"""
        return self._published_list_response(Article.published.trending())

    @action(detail=False, permission_classes=[permissions.IsAuthenticated])
    def bookmarked(self, request):
        """Articles bookmarked by the current user"""
        queryset = Article.published.filter(bookmarks__user=request.user).order_by("-bookmarks__created_at")
        page = self.paginate_queryset(queryset.with_related().with_user_flags(request.user))
        serializer = ArticleListSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """API ViewSet for Category operations"""

    queryset = Category.objects.active().with_article_count()
    serializer_class = CategorySerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "description"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return CategoryCreateUpdateSerializer
        return CategorySerializer

    @action(detail=True)
    def articles(self, request, pk=None):
        """Get articles for a category"""
        category = self.get_object()
        articles = Article.published.filter(category=category).with_related().with_user_flags(request.user)
        serializer = ArticleListSerializer(articles, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    """API ViewSet for Tag operations"""

    queryset = Tag.objects.with_article_count()
    serializer_class = TagSerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering = ["name"]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return TagCreateUpdateSerializer
        return TagSerializer

    @action(detail=False)
    def popular(self, request):
        """Get popular tags"""
        serializer = TagSerializer(Tag.objects.popular(20), many=True, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=True)
    def articles(self, request, pk=None):
        """Get articles for a tag"""
        tag = self.get_object()
        articles = Article.published.filter(tags=tag).with_related().with_user_flags(request.user)
        serializer = ArticleListSerializer(articles, many=True, context=self.get_serializer_context())
        return Response(serializer.data)


# ──────────────────────────────────────────────────────────────────────────────
# Function-based views
# ──────────────────────────────────────────────────────────────────────────────


@cache_page(60 * 15)
def trending_articles_view(request):
    """Display trending articles"""
    trending_articles = Article.published.trending().with_related()[:20]
    return render(
        request,
        "articles/trending.html",
        {
            "articles": trending_articles,
            "title": "Trending Articles",
        },
    )


def search_view(request):
    """Search articles"""
    query = request.GET.get("q", "").strip()
    page_obj = None
    results = []

    if query:
        paginator = Paginator(search_all(query, filters=request.GET.dict()), 10)
        page_obj = paginator.get_page(request.GET.get("page"))
        results = page_obj.object_list

    return render(
        request,
        "articles/search_results.html",
        {
            "query": query,
            "results": results,
            "page_obj": page_obj,
            "is_paginated": page_obj is not None and page_obj.has_other_pages(),
            "search_form": ArticleSearchForm(request.GET),
        },
    )


def autocomplete_view(request):
    """AJAX autocomplete for search"""
    query = request.GET.get("q", "").strip()
    if not query or len(query) < 2:
        return JsonResponse({"suggestions": []})
    return JsonResponse({"suggestions": ArticleSearchManager.search_autocomplete(query)})


# ──────────────────────────────────────────────────────────────────────────────
# Category / Tag web views
# ──────────────────────────────────────────────────────────────────────────────


class CategoryListView(ListView):
    """List all active categories"""

    model = Category
    template_name = "articles/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.active().with_article_count().order_by("name")


class CategoryDetailView(DetailView):
    """Articles grouped under one category"""

    model = Category
    template_name = "articles/category_detail.html"
    context_object_name = "category"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    paginate_by = 12

    def get_queryset(self):
        return Category.objects.active()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        articles = (
            Article.published.filter(category=self.object)
            .with_related()
            .with_user_flags(self.request.user)
            .order_by("-published_at")
        )
        page_obj = Paginator(articles, self.paginate_by).get_page(self.request.GET.get("page"))
        context.update(
            {"articles": page_obj.object_list, "page_obj": page_obj, "is_paginated": page_obj.has_other_pages()}
        )
        return context


class TagListView(ListView):
    """List all tags ordered by popularity"""

    model = Tag
    template_name = "articles/tag_list.html"
    context_object_name = "tags"

    def get_queryset(self):
        return Tag.objects.with_article_count().order_by("-article_count", "name")


class TagDetailView(DetailView):
    """Articles grouped under one tag"""

    model = Tag
    template_name = "articles/tag_detail.html"
    context_object_name = "tag"
    slug_field = "slug"
    slug_url_kwarg = "slug"
    paginate_by = 12

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        articles = (
            Article.published.filter(tags=self.object)
            .with_related()
            .with_user_flags(self.request.user)
            .order_by("-published_at")
        )
        page_obj = Paginator(articles, self.paginate_by).get_page(self.request.GET.get("page"))
        context.update(
            {"articles": page_obj.object_list, "page_obj": page_obj, "is_paginated": page_obj.has_other_pages()}
        )
        return context
