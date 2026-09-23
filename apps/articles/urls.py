# File: DjangoVerseHub/apps/articles/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = 'articles'

# API router
router = DefaultRouter()
router.register(r'articles', views.ArticleViewSet, basename='article')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'tags', views.TagViewSet, basename='tag')

urlpatterns = [
    # Web views
    path('', views.ArticleListView.as_view(), name='list'),
    path('create/', views.ArticleCreateView.as_view(), name='create'),
    path('mine/', views.MyArticlesView.as_view(), name='my_articles'),
    path('drafts/', views.DraftsView.as_view(), name='drafts'),
    path('bookmarks/', views.BookmarksView.as_view(), name='bookmarks'),
    path('search/', views.search_view, name='search'),
    path('trending/', views.trending_articles_view, name='trending'),
    path('autocomplete/', views.autocomplete_view, name='autocomplete'),

    # Category views
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('category/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),

    # Tag views
    path('tags/', views.TagListView.as_view(), name='tags'),
    path('tag/<slug:slug>/', views.TagDetailView.as_view(), name='tag_detail'),

    # API endpoints
    path('api/', include(router.urls)),

    # Article CRUD and engagement (slug-based; keep these last so fixed prefixes win)
    path('<slug:slug>/', views.ArticleDetailView.as_view(), name='detail'),
    path('<slug:slug>/edit/', views.ArticleUpdateView.as_view(), name='edit'),
    path('<slug:slug>/delete/', views.ArticleDeleteView.as_view(), name='delete'),
    path('<slug:slug>/like/', views.article_like_view, name='like'),
    path('<slug:slug>/bookmark/', views.article_bookmark_view, name='bookmark'),
    path('<slug:slug>/revisions/', views.ArticleRevisionListView.as_view(), name='revisions'),
    path('<slug:slug>/revisions/<int:pk>/restore/', views.article_revision_restore_view, name='revision_restore'),
]
