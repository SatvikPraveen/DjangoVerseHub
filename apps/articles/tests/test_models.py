# File: DjangoVerseHub/apps/articles/tests/test_models.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.articles.models import Article, Category, Tag

User = get_user_model()


class CategoryModelTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name='Technology',
            description='Tech articles'
        )

    def test_category_creation(self):
        self.assertEqual(self.category.name, 'Technology')
        self.assertEqual(self.category.slug, 'technology')
        self.assertTrue(self.category.is_active)

    def test_category_str(self):
        self.assertEqual(str(self.category), 'Technology')

    def test_category_absolute_url(self):
        self.assertEqual(
            self.category.get_absolute_url(),
            f'/articles/category/{self.category.slug}/'
        )

    def test_article_count_property(self):
        user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        Article.objects.create(
            title='Test Article',
            content='Test content',
            author=user,
            category=self.category,
            status='published'
        )
        self.assertEqual(self.category.article_count, 1)


class TagModelTest(TestCase):
    def setUp(self):
        self.tag = Tag.objects.create(name='Python')

    def test_tag_creation(self):
        self.assertEqual(self.tag.name, 'Python')
        self.assertEqual(self.tag.slug, 'python')

    def test_tag_str(self):
        self.assertEqual(str(self.tag), 'Python')

    def test_tag_absolute_url(self):
        self.assertEqual(
            self.tag.get_absolute_url(),
            f'/articles/tag/{self.tag.slug}/'
        )


class ArticleModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='author@example.com',
            first_name='John',
            last_name='Doe'
        )
        self.category = Category.objects.create(
            name='Programming',
            description='Programming tutorials'
        )
        self.tag = Tag.objects.create(name='Django')
        
        self.article = Article.objects.create(
            title='Django Testing Guide',
            content='This is a comprehensive guide to testing in Django.' * 10,
            author=self.user,
            category=self.category,
            status='published'
        )
        self.article.tags.add(self.tag)

    def test_article_creation(self):
        self.assertEqual(self.article.title, 'Django Testing Guide')
        self.assertEqual(self.article.slug, 'django-testing-guide')
        self.assertEqual(self.article.author, self.user)
        self.assertEqual(self.article.category, self.category)
        self.assertEqual(self.article.status, 'published')

    def test_article_str(self):
        self.assertEqual(str(self.article), 'Django Testing Guide')

    def test_article_absolute_url(self):
        self.assertEqual(
            self.article.get_absolute_url(),
            f'/articles/{self.article.slug}/'
        )

    def test_is_published_property(self):
        self.assertTrue(self.article.is_published)
        
        self.article.status = 'draft'
        self.article.save()
        self.assertFalse(self.article.is_published)

    def test_reading_time_property(self):
        reading_time = self.article.reading_time
        self.assertIsInstance(reading_time, int)
        self.assertGreater(reading_time, 0)

    def test_increment_views(self):
        initial_views = self.article.views_count
        self.article.increment_views()
        self.assertEqual(self.article.views_count, initial_views + 1)

    def test_get_related_articles(self):
        # Create another article with same tag
        Article.objects.create(
            title='Django Models Guide',
            content='Guide to Django models',
            author=self.user,
            status='published'
        ).tags.add(self.tag)
        
        related = self.article.get_related_articles()
        self.assertEqual(len(related), 1)

    def test_meta_description_auto_generation(self):
        article = Article.objects.create(
            title='Auto Meta Test',
            content='This is test content for meta description generation.' * 10,
            author=self.user,
            status='published'
        )
        self.assertTrue(article.meta_description)
        self.assertTrue(len(article.meta_description) <= 160)

    def test_published_at_auto_set(self):
        article = Article.objects.create(
            title='Published Date Test',
            content='Test content',
            author=self.user,
            status='draft'
        )
        self.assertIsNone(article.published_at)
        
        article.status = 'published'
        article.save()
        self.assertIsNotNone(article.published_at)

    def test_unique_slug_generation(self):
        # Create another article with same title
        article2 = Article.objects.create(
            title='Django Testing Guide',
            content='Different content',
            author=self.user,
            status='published'
        )
        self.assertNotEqual(self.article.slug, article2.slug)
        self.assertTrue(article2.slug.startswith('django-testing-guide'))


class ArticleManagerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        # Create published article
        self.published_article = Article.objects.create(
            title='Published Article',
            content='Published content',
            author=self.user,
            status='published'
        )
        
        # Create draft article
        self.draft_article = Article.objects.create(
            title='Draft Article',
            content='Draft content',
            author=self.user,
            status='draft'
        )

    def test_published_manager(self):
        published_articles = Article.published.all()
        self.assertIn(self.published_article, published_articles)
        self.assertNotIn(self.draft_article, published_articles)

    def test_draft_manager(self):
        draft_articles = Article.objects.draft()
        self.assertIn(self.draft_article, draft_articles)
        self.assertNotIn(self.published_article, draft_articles)

    def test_search_manager(self):
        search_results = Article.objects.search('Published')
        self.assertIn(self.published_article, search_results)
        
        search_results = Article.objects.search('Nonexistent')
        self.assertEqual(search_results.count(), 0)

    def test_popular_manager(self):
        # Increase views for one article
        self.published_article.views_count = 100
        self.published_article.save()
        
        popular_articles = Article.objects.popular()
        self.assertEqual(popular_articles.first(), self.published_article)

    def test_trending_manager(self):
        # Create recent article with high engagement
        recent_article = Article.objects.create(
            title='Trending Article',
            content='Trending content',
            author=self.user,
            status='published',
            views_count=50,
            likes_count=25
        )
        
        trending_articles = Article.objects.trending(days=30)
        self.assertIn(recent_article, trending_articles)

    def test_by_category_manager(self):
        category = Category.objects.create(name='Test Category')
        self.published_article.category = category
        self.published_article.save()
        
        category_articles = Article.objects.by_category('test-category')
        self.assertIn(self.published_article, category_articles)

    def test_by_tag_manager(self):
        tag = Tag.objects.create(name='Test Tag')
        self.published_article.tags.add(tag)
        
        tag_articles = Article.objects.by_tag('test-tag')
        self.assertIn(self.published_article, tag_articles)