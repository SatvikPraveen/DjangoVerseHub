# File: DjangoVerseHub/apps/articles/urls.py

from django.urls import path, include
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
    path('search/', views.search_view, name='search'),
    path('trending/', views.trending_articles_view, name='trending'),
    path('autocomplete/', views.autocomplete_view, name='autocomplete'),
    
    # Category views
    path('categories/', views.CategoryListView.as_view(), name='category_list'),
    path('category/<slug:slug>/', views.CategoryDetailView.as_view(), name='category_detail'),
    
    # Article CRUD
    path('<slug:slug>/', views.ArticleDetailView.as_view(), name='detail'),
    path('<slug:slug>/edit/', views.ArticleUpdateView.as_view(), name='edit'),
    path('<slug:slug>/delete/', views.ArticleDeleteView.as_view(), name='delete'),
    
    # API endpoints
    path('api/', include(router.urls)),
]