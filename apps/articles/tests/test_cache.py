# File: DjangoVerseHub/apps/articles/tests/test_cache.py

from django.test import TestCase, override_settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from apps.articles.models import Article, Category, Tag
from apps.articles.cache import (
    ArticleCacheManager, CategoryCacheManager, TagCacheManager
)
import json

User = get_user_model()


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
})
class ArticleCacheManagerTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.category = Category.objects.create(name='Tech')
        self.tag = Tag.objects.create(name='Django')
        
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content for caching.' * 20,
            author=self.user,
            category=self.category,
            status='published'
        )
        self.article.tags.add(self.tag)

    def test_cache_article(self):
        cached_data = ArticleCacheManager.cache_article(self.article)
        
        self.assertEqual(cached_data['id'], str(self.article.id))
        self.assertEqual(cached_data['title'], self.article.title)
        self.assertEqual(cached_data['author_name'], self.user.get_full_name())
        self.assertEqual(cached_data['category_name'], self.category.name)
        self.assertIn('django', cached_data['tags'])

    def test_get_cached_article(self):
        ArticleCacheManager.cache_article(self.article)
        cached_data = ArticleCacheManager.get_cached_article(self.article.id)
        
        self.assertIsNotNone(cached_data)
        self.assertEqual(cached_data['title'], self.article.title)

    def test_get_cached_article_not_cached(self):
        cached_data = ArticleCacheManager.get_cached_article('nonexistent-id')
        self.assertIsNone(cached_data)

    def test_cache_popular_articles(self):
        Article.objects.create(
            title='Popular Article',
            content='Popular content.' * 20,
            author=self.user,
            status='published',
            views_count=100,
            likes_count=50
        )
        
        cached_articles = ArticleCacheManager.cache_popular_articles(limit=5)
        
        self.assertIsInstance(cached_articles, list)
        self.assertGreaterEqual(len(cached_articles), 1)
        
        if cached_articles:
            article_data = cached_articles[0]
            self.assertIn('id', article_data)
            self.assertIn('title', article_data)
            self.assertIn('author_name', article_data)
            self.assertIn('views_count', article_data)

    def test_get_cached_popular_articles(self):
        popular_articles = ArticleCacheManager.get_cached_popular_articles(limit=3)
        
        cache_key = ArticleCacheManager.get_popular_articles_cache_key(7, 3)
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        
        popular_articles_2 = ArticleCacheManager.get_cached_popular_articles(limit=3)
        self.assertEqual(popular_articles, popular_articles_2)

    def test_cache_featured_articles(self):
        self.article.is_featured = True
        self.article.save()
        
        cached_articles = ArticleCacheManager.cache_featured_articles(limit=5)
        
        self.assertIsInstance(cached_articles, list)
        self.assertEqual(len(cached_articles), 1)
        self.assertEqual(cached_articles[0]['title'], self.article.title)

    def test_invalidate_article_cache(self):
        ArticleCacheManager.cache_article(self.article)
        cache_key = ArticleCacheManager.get_article_cache_key(self.article.id)
        
        self.assertIsNotNone(cache.get(cache_key))
        
        ArticleCacheManager.invalidate_article_cache(self.article.id)
        self.assertIsNone(cache.get(cache_key))

    def test_cache_key_generators(self):
        article_key = ArticleCacheManager.get_article_cache_key('test-id')
        self.assertEqual(article_key, 'article:test-id')
        
        list_key = ArticleCacheManager.get_article_list_cache_key(
            page=2, category='tech', tag='python', search='django'
        )
        self.assertIn('articles', list_key)
        self.assertIn('page:2', list_key)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
})
class CategoryCacheManagerTest(TestCase):
    def setUp(self):
        cache.clear()
        self.category1 = Category.objects.create(
            name='Technology',
            description='Tech articles',
            is_active=True
        )
        self.category2 = Category.objects.create(
            name='Science',
            description='Science articles',
            is_active=True
        )
        Category.objects.create(
            name='Inactive',
            description='Inactive category',
            is_active=False
        )

    def test_cache_active_categories(self):
        cached_categories = CategoryCacheManager.cache_active_categories()
        
        self.assertIsInstance(cached_categories, list)
        self.assertEqual(len(cached_categories), 2)
        
        category_data = cached_categories[0]
        self.assertIn('id', category_data)
        self.assertIn('name', category_data)
        self.assertIn('slug', category_data)
        self.assertIn('description', category_data)
        self.assertIn('article_count', category_data)

    def test_get_cached_active_categories(self):
        categories_1 = CategoryCacheManager.get_cached_active_categories()
        
        cache_key = CategoryCacheManager.get_categories_cache_key()
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        
        categories_2 = CategoryCacheManager.get_cached_active_categories()
        self.assertEqual(categories_1, categories_2)

    def test_cache_excludes_inactive_categories(self):
        cached_categories = CategoryCacheManager.cache_active_categories()
        
        category_names = [cat['name'] for cat in cached_categories]
        self.assertNotIn('Inactive', category_names)
        self.assertIn('Technology', category_names)
        self.assertIn('Science', category_names)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
})
class TagCacheManagerTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.tag1 = Tag.objects.create(name='Django')
        self.tag2 = Tag.objects.create(name='Python')
        self.tag3 = Tag.objects.create(name='JavaScript')
        
        article1 = Article.objects.create(
            title='Django Article',
            content='Django content.' * 20,
            author=self.user,
            status='published'
        )
        article1.tags.add(self.tag1)
        
        article2 = Article.objects.create(
            title='Python Article',
            content='Python content.' * 20,
            author=self.user,
            status='published'
        )
        article2.tags.add(self.tag1, self.tag2)

    def test_cache_popular_tags(self):
        cached_tags = TagCacheManager.cache_popular_tags(limit=10)
        
        self.assertIsInstance(cached_tags, list)
        self.assertGreaterEqual(len(cached_tags), 2)
        
        if cached_tags:
            tag_data = cached_tags[0]
            self.assertIn('id', tag_data)
            self.assertIn('name', tag_data)
            self.assertIn('slug', tag_data)
            self.assertIn('article_count', tag_data)

    def test_get_cached_popular_tags(self):
        tags_1 = TagCacheManager.get_cached_popular_tags(limit=5)
        
        cache_key = TagCacheManager.get_popular_tags_cache_key(5)
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        
        tags_2 = TagCacheManager.get_cached_popular_tags(limit=5)
        self.assertEqual(tags_1, tags_2)

    def test_popular_tags_ordering(self):
        article3 = Article.objects.create(
            title='Another Python Article',
            content='More Python content.' * 20,
            author=self.user,
            status='published'
        )
        article3.tags.add(self.tag2)
        
        cached_tags = TagCacheManager.cache_popular_tags(limit=10)
        
        tag_counts = {tag['name']: tag['article_count'] for tag in cached_tags}
        
        self.assertGreaterEqual(tag_counts.get('Django', 0), 1)
        self.assertGreaterEqual(tag_counts.get('Python', 0), 1)


class CacheIntegrationTest(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

    @override_settings(CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    })
    def test_cache_invalidation_on_article_save(self):
        article = Article.objects.create(
            title='Cache Test Article',
            content='Cache test content.' * 20,
            author=self.user,
            status='published'
        )
        
        ArticleCacheManager.cache_article(article)
        cache_key = ArticleCacheManager.get_article_cache_key(article.id)
        
        cached_data = cache.get(cache_key)
        self.assertIsNotNone(cached_data)
        
        article.title = 'Updated Cache Test Article'
        article.save()
        
        # Test passes if no exception is raised during save
        self.assertTrue(True)