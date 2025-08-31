# File: DjangoVerseHub/apps/articles/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q, F
from django.core.paginator import Paginator
from django.http import JsonResponse, Http404
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Article, Category, Tag
from .forms import ArticleForm, ArticleSearchForm, CategoryForm, TagForm
from .serializers import (
    ArticleListSerializer, ArticleDetailSerializer, ArticleCreateUpdateSerializer,
    CategorySerializer, TagSerializer, ArticleSearchSerializer, PopularArticleSerializer
)
from .search import search_all, ArticleSearchManager
from .pagination import ArticlePaginator
from .cache import ArticleCacheManager
from django_verse_hub.permissions import IsOwnerOrReadOnly, IsStaffOrReadOnly


# Class-Based Views
class ArticleListView(ListView):
    """List all published articles"""
    model = Article
    template_name = 'articles/article_list.html'
    context_object_name = 'articles'
    paginate_by = 12

    def get_queryset(self):
        queryset = Article.published.select_related('author', 'category').prefetch_related('tags')
        
        # Apply search
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = search_all(search_query)
        
        # Apply category filter
        category_slug = self.request.GET.get('category')
        if category_slug:
            queryset = queryset.filter(category__slug=category_slug)
        
        # Apply tag filter
        tag_slug = self.request.GET.get('tag')
        if tag_slug:
            queryset = queryset.filter(tags__slug=tag_slug)
        
        # Apply ordering
        ordering = self.request.GET.get('ordering', '-created_at')
        if ordering in ['-created_at', 'created_at', '-views_count', '-likes_count', 'title', '-title']:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = ArticleSearchForm(self.request.GET)
        context['categories'] = Category.objects.active()[:10]
        context['popular_tags'] = Tag.objects.popular()[:20]
        context['featured_articles'] = ArticleCacheManager.get_cached_featured_articles()[:3]
        return context


class ArticleDetailView(DetailView):
    """Display single article"""
    model = Article
    template_name = 'articles/article_detail.html'
    context_object_name = 'article'

    def get_queryset(self):
        return Article.published.select_related('author', 'category').prefetch_related('tags', 'comments__author')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.increment_views()
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object
        context['related_articles'] = article.get_related_articles()
        context['comments'] = article.comments.filter(is_active=True, parent=None).select_related('author')[:10]
        return context


class ArticleCreateView(LoginRequiredMixin, CreateView):
    """Create new article"""
    model = Article
    form_class = ArticleForm
    template_name = 'articles/article_create.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.author = self.request.user
        messages.success(self.request, 'Article created successfully!')
        return super().form_valid(form)


class ArticleUpdateView(LoginRequiredMixin, UpdateView):
    """Update existing article"""
    model = Article
    form_class = ArticleForm
    template_name = 'articles/article_edit.html'

    def get_queryset(self):
        return Article.objects.filter(author=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Article updated successfully!')
        return super().form_valid(form)


# API ViewSets
class ArticleViewSet(viewsets.ModelViewSet):
    """API ViewSet for Article operations"""
    queryset = Article.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'category', 'tags', 'is_featured']
    search_fields = ['title', 'content', 'summary']
    ordering_fields = ['created_at', 'published_at', 'views_count', 'likes_count']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == 'list':
            if not (self.request.user.is_authenticated and self.request.user.is_staff):
                queryset = queryset.filter(status='published')
        return queryset.select_related('author', 'category').prefetch_related('tags')

    def get_serializer_class(self):
        if self.action == 'list':
            return ArticleListSerializer
        elif self.action == 'retrieve':
            return ArticleDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ArticleCreateUpdateSerializer
        return ArticleDetailSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'])
    def increment_views(self, request, pk=None):
        """Increment article view count"""
        article = self.get_object()
        article.increment_views()
        return Response({'views_count': article.views_count})

    @action(detail=False)
    def featured(self, request):
        """Get featured articles"""
        articles = Article.published.featured().select_related('author', 'category')[:10]
        serializer = ArticleListSerializer(articles, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False)
    def popular(self, request):
        """Get popular articles"""
        articles = Article.published.popular().select_related('author', 'category')[:10]
        serializer = PopularArticleSerializer(articles, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False)
    def trending(self, request):
        """Get trending articles"""
        articles = Article.published.trending().select_related('author', 'category')[:10]
        serializer = ArticleListSerializer(articles, many=True, context={'request': request})
        return Response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """API ViewSet for Category operations"""
    queryset = Category.objects.active()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']

    @action(detail=True)
    def articles(self, request, pk=None):
        """Get articles for a category"""
        category = self.get_object()
        articles = Article.published.filter(category=category).select_related('author')
        serializer = ArticleListSerializer(articles, many=True, context={'request': request})
        return Response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    """API ViewSet for Tag operations"""
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsStaffOrReadOnly]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name']
    ordering = ['name']

    @action(detail=False)
    def popular(self, request):
        """Get popular tags"""
        tags = Tag.objects.popular()[:20]
        serializer = self.get_serializer(tags, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def articles(self, request, pk=None):
        """Get articles for a tag"""
        tag = self.get_object()
        articles = Article.published.filter(tags=tag).select_related('author', 'category')
        serializer = ArticleListSerializer(articles, many=True, context={'request': request})
        return Response(serializer.data)


# Function-Based Views
@cache_page(60 * 15)
def trending_articles_view(request):
    """Display trending articles"""
    trending_articles = Article.published.trending().select_related('author', 'category')[:20]
    return render(request, 'articles/trending.html', {
        'articles': trending_articles,
        'title': 'Trending Articles'
    })


def search_view(request):
    """Search articles"""
    query = request.GET.get('q', '').strip()
    results = []
    
    if query:
        results = search_all(query, filters=request.GET.dict())
        paginator = Paginator(results, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        results = page_obj.object_list
    else:
        page_obj = None
    
    return render(request, 'articles/search_results.html', {
        'query': query,
        'results': results,
        'page_obj': page_obj,
        'search_form': ArticleSearchForm(request.GET)
    })


def autocomplete_view(request):
    """AJAX autocomplete for search"""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'suggestions': []})
    
    suggestions = ArticleSearchManager.search_autocomplete(query)
    return JsonResponse({'suggestions': suggestions})