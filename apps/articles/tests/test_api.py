# File: DjangoVerseHub/apps/articles/tests/test_api.py

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from apps.articles.models import Article, Category, Tag
import json

User = get_user_model()


class ArticleAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
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
        self.token = Token.objects.create(user=self.user)
        self.category = Category.objects.create(name='Tech')
        self.tag = Tag.objects.create(name='Django')
        
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content for API testing.' * 20,
            author=self.user,
            category=self.category,
            status='published'
        )
        self.article.tags.add(self.tag)

    def test_get_articles_list(self):
        url = reverse('articles:article-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Test Article')

    def test_get_article_detail(self):
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Article')
        self.assertIn('content', response.data)
        self.assertIn('author', response.data)
        self.assertIn('category', response.data)
        self.assertIn('tags', response.data)

    def test_create_article_authenticated(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('articles:article-list')
        data = {
            'title': 'New Article via API',
            'content': 'This is new content created via API.' * 20,
            'category': self.category.id,
            'tags': [self.tag.id],
            'status': 'published',
            'allow_comments': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Article.objects.count(), 2)
        new_article = Article.objects.get(title='New Article via API')
        self.assertEqual(new_article.author, self.user)

    def test_create_article_unauthenticated(self):
        url = reverse('articles:article-list')
        data = {
            'title': 'Unauthorized Article',
            'content': 'This should not be created.' * 20
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_article_invalid_data(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('articles:article-list')
        data = {
            'title': '',  # Invalid - empty title
            'content': 'Short'  # Invalid - too short
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('title', response.data)
        self.assertIn('content', response.data)

    def test_update_article_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        data = {
            'title': 'Updated Article Title',
            'content': 'Updated content for the article.' * 20,
            'status': 'published'
        }
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, 'Updated Article Title')

    def test_update_article_not_owner(self):
        other_token = Token.objects.create(user=self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + other_token.key)
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        data = {'title': 'Unauthorized Update'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_article_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Article.objects.filter(pk=self.article.pk).exists())

    def test_delete_article_not_owner(self):
        other_token = Token.objects.create(user=self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + other_token.key)
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_article_search(self):
        url = reverse('articles:article-list')
        response = self.client.get(url, {'search': 'Test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_article_filter_by_category(self):
        url = reverse('articles:article-list')
        response = self.client.get(url, {'category': self.category.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_article_filter_by_tag(self):
        url = reverse('articles:article-list')
        response = self.client.get(url, {'tags': self.tag.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_article_ordering(self):
        # Create another article
        Article.objects.create(
            title='Second Article',
            content='Second article content.' * 20,
            author=self.user,
            status='published',
            views_count=100
        )
        
        url = reverse('articles:article-list')
        response = self.client.get(url, {'ordering': '-views_count'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['title'], 'Second Article')

    def test_increment_views_action(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('articles:article-increment-views', kwargs={'pk': self.article.pk})
        initial_views = self.article.views_count
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['views_count'], initial_views + 1)

    def test_featured_articles_action(self):
        self.article.is_featured = True
        self.article.save()
        
        url = reverse('articles:article-featured')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Test Article')

    def test_popular_articles_action(self):
        self.article.views_count = 100
        self.article.likes_count = 50
        self.article.save()
        
        url = reverse('articles:article-popular')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_trending_articles_action(self):
        url = reverse('articles:article-trending')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)


class CategoryAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            first_name='Staff',
            last_name='User',
            is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.staff_token = Token.objects.create(user=self.staff_user)
        
        self.category = Category.objects.create(
            name='Technology',
            description='Tech articles'
        )

    def test_get_categories_list(self):
        url = reverse('articles:category-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Technology')

    def test_create_category_staff_user(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.staff_token.key)
        url = reverse('articles:category-list')
        data = {
            'name': 'Science',
            'description': 'Science articles',
            'is_active': True
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Category.objects.count(), 2)

    def test_create_category_regular_user(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('articles:category-list')
        data = {
            'name': 'Unauthorized Category',
            'description': 'Should not be created'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_category_articles_action(self):
        article = Article.objects.create(
            title='Tech Article',
            content='Tech content.' * 20,
            author=self.user,
            category=self.category,
            status='published'
        )
        
        url = reverse('articles:category-articles', kwargs={'pk': self.category.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Tech Article')


class TagAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            first_name='Staff',
            last_name='User',
            is_staff=True
        )
        self.token = Token.objects.create(user=self.user)
        self.staff_token = Token.objects.create(user=self.staff_user)
        
        self.tag = Tag.objects.create(name='Django')

    def test_get_tags_list(self):
        url = reverse('articles:tag-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Django')

    def test_popular_tags_action(self):
        # Create article with tag to make it popular
        article = Article.objects.create(
            title='Django Article',
            content='Django content.' * 20,
            author=self.user,
            status='published'
        )
        article.tags.add(self.tag)
        
        url = reverse('articles:tag-popular')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_tag_articles_action(self):
        article = Article.objects.create(
            title='Django Tutorial',
            content='Django tutorial content.' * 20,
            author=self.user,
            status='published'
        )
        article.tags.add(self.tag)
        
        url = reverse('articles:tag-articles', kwargs={'pk': self.tag.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Django Tutorial')

    def test_create_tag_staff_user(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.staff_token.key)
        url = reverse('articles:tag-list')
        data = {'name': 'Python'}
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tag.objects.count(), 2)

    def test_search_tags(self):
        url = reverse('articles:tag-list')
        response = self.client.get(url, {'search': 'Django'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)