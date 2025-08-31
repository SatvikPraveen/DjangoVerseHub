# File: DjangoVerseHub/apps/articles/tests/test_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.articles.models import Article, Category, Tag

User = get_user_model()


class ArticleListViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content',
            author=self.user,
            status='published'
        )
        self.url = reverse('articles:list')

    def test_article_list_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Article')
        self.assertIn('articles', response.context)

    def test_article_list_view_pagination(self):
        # Create multiple articles
        for i in range(15):
            Article.objects.create(
                title=f'Test Article {i}',
                content=f'Test content {i}',
                author=self.user,
                status='published'
            )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_paginated'])

    def test_article_list_search(self):
        response = self.client.get(self.url, {'q': 'Test'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Article')

    def test_article_list_category_filter(self):
        category = Category.objects.create(name='Tech')
        self.article.category = category
        self.article.save()
        
        response = self.client.get(self.url, {'category': 'tech'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Article')

    def test_article_list_tag_filter(self):
        tag = Tag.objects.create(name='Django')
        self.article.tags.add(tag)
        
        response = self.client.get(self.url, {'tag': 'django'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Article')


class ArticleDetailViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content',
            author=self.user,
            status='published'
        )
        self.url = reverse('articles:detail', kwargs={'slug': self.article.slug})

    def test_article_detail_view_get(self):
        initial_views = self.article.views_count
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Article')
        self.assertContains(response, 'Test content')
        
        # Check that view count was incremented
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, initial_views + 1)

    def test_article_detail_view_404(self):
        url = reverse('articles:detail', kwargs={'slug': 'nonexistent'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_article_detail_context(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('article', response.context)
        self.assertIn('related_articles', response.context)
        self.assertIn('comments', response.context)


class ArticleCreateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.category = Category.objects.create(name='Tech')
        self.url = reverse('articles:create')

    def test_article_create_view_anonymous(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_article_create_view_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create New Article')

    def test_article_create_post_valid(self):
        self.client.force_login(self.user)
        data = {
            'title': 'New Test Article',
            'content': 'This is the content of the new test article.' * 10,
            'category': self.category.id,
            'status': 'published',
            'allow_comments': True
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, 302)  # Redirect after creation
        self.assertTrue(Article.objects.filter(title='New Test Article').exists())

    def test_article_create_post_invalid(self):
        self.client.force_login(self.user)
        data = {
            'title': '',  # Invalid - empty title
            'content': 'Short',  # Invalid - too short
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, 200)  # Stay on form with errors
        self.assertFormError(response, 'form', 'title', 'This field is required.')


class ArticleUpdateViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            first_name='Other',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content' * 20,
            author=self.user,
            status='published'
        )
        self.url = reverse('articles:edit', kwargs={'slug': self.article.slug})

    def test_article_update_view_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Article')

    def test_article_update_view_not_owner(self):
        self.client.force_login(self.other_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_article_update_post_valid(self):
        self.client.force_login(self.user)
        data = {
            'title': 'Updated Test Article',
            'content': 'Updated test content' * 20,
            'status': 'published',
            'allow_comments': True
        }
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, 'Updated Test Article')


class ArticleDeleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content',
            author=self.user,
            status='published'
        )
        self.url = reverse('articles:delete', kwargs={'slug': self.article.slug})

    def test_article_delete_view_get(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Are you sure')

    def test_article_delete_post(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Article.objects.filter(id=self.article.id).exists())


class CategoryViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.category = Category.objects.create(
            name='Technology',
            description='Tech articles'
        )
        self.article = Article.objects.create(
            title='Tech Article',
            content='Tech content',
            author=self.user,
            category=self.category,
            status='published'
        )

    def test_category_list_view(self):
        url = reverse('articles:category_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Technology')

    def test_category_detail_view(self):
        url = reverse('articles:category_detail', kwargs={'slug': self.category.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Technology')
        self.assertContains(response, 'Tech Article')


class SearchViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Django Tutorial',
            content='Learn Django framework',
            author=self.user,
            status='published'
        )
        self.url = reverse('articles:search')

    def test_search_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_search_view_with_query(self):
        response = self.client.get(self.url, {'q': 'Django'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Django Tutorial')

    def test_search_view_no_results(self):
        response = self.client.get(self.url, {'q': 'NonexistentTopic'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Django Tutorial')


class AutocompleteViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Django Tutorial',
            content='Learn Django',
            author=self.user,
            status='published'
        )
        self.url = reverse('articles:autocomplete')

    def test_autocomplete_view_json_response(self):
        response = self.client.get(self.url, {'q': 'Django'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_autocomplete_view_short_query(self):
        response = self.client.get(self.url, {'q': 'D'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['suggestions'], [])


class TrendingViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.article = Article.objects.create(
            title='Trending Article',
            content='Trending content',
            author=self.user,
            status='published',
            views_count=100
        )
        self.url = reverse('articles:trending')

    def test_trending_view_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Trending Articles')