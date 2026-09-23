# File: DjangoVerseHub/apps/api/tests/test_views.py

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from apps.articles.models import Article, Category, Tag

User = get_user_model()


class APIRootTests(APITestCase):
    def test_root_lists_endpoints_and_docs(self):
        response = self.client.get(reverse('api:api_root'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('articles', response.data['endpoints'])
        self.assertIn('jwt', response.data['authentication'])
        self.assertTrue(response.data['docs'].endswith('/api/v1/docs/'))


class AuthAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='auth@example.com', username='auth', password='Secret123!')

    def test_token_login_success(self):
        response = self.client.post(reverse('api:auth_login'), {'email': 'AUTH@example.com', 'password': 'Secret123!'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['token'], Token.objects.get(user=self.user).key)
        self.assertEqual(response.data['user']['username'], 'auth')

    def test_token_login_bad_password(self):
        response = self.client.post(reverse('api:auth_login'), {'email': 'auth@example.com', 'password': 'nope'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['error']['code'], 'validation_error')

    def test_token_login_disabled_account(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(reverse('api:auth_login'), {'email': 'auth@example.com', 'password': 'Secret123!'})
        self.assertEqual(response.status_code, 400)

    def test_logout_revokes_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post(reverse('api:auth_logout'))
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Token.objects.filter(user=self.user).exists())

    def test_jwt_flow(self):
        create = self.client.post(reverse('api:jwt_create'), {'email': 'auth@example.com', 'password': 'Secret123!'})
        self.assertEqual(create.status_code, 200)
        access, refresh = create.data['access'], create.data['refresh']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        dashboard = self.client.get(reverse('api:user_dashboard'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data['user']['email'], 'auth@example.com')

        self.client.credentials()
        refreshed = self.client.post(reverse('api:jwt_refresh'), {'refresh': refresh})
        self.assertEqual(refreshed.status_code, 200)
        self.assertIn('access', refreshed.data)
        # Rotation + blacklist: the old refresh token is no longer usable
        reused = self.client.post(reverse('api:jwt_refresh'), {'refresh': refresh})
        self.assertEqual(reused.status_code, 401)

    def test_jwt_verify_rejects_garbage(self):
        response = self.client.post(reverse('api:jwt_verify'), {'token': 'not-a-token'})
        self.assertEqual(response.status_code, 401)


class SearchAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(email='w@example.com', username='writer', password='x', first_name='Wren')
        cls.private = User.objects.create_user(email='p@example.com', username='private', password='x', first_name='Wrenna')
        cls.private.profile.is_public = False
        cls.private.profile.save()
        cls.category = Category.objects.create(name='Async', slug='async')
        cls.tag = Tag.objects.create(name='asyncio', slug='asyncio')
        article = Article.objects.create(title='Async Django', content='...', author=cls.author, category=cls.category, status='published')
        article.tags.add(cls.tag)
        Article.objects.create(title='Async draft', content='...', author=cls.author, status='draft')

    def setUp(self):
        cache.clear()

    def test_requires_query(self):
        response = self.client.get(reverse('api:search'))
        self.assertEqual(response.status_code, 400)

    def test_search_all(self):
        response = self.client.get(reverse('api:search'), {'q': 'async'})
        self.assertEqual(response.status_code, 200)
        titles = [a['title'] for a in response.data['results']['articles']]
        self.assertEqual(titles, ['Async Django'])
        self.assertEqual(response.data['results']['tags'][0]['article_count'], 1)

    def test_private_profiles_hidden_from_user_search(self):
        response = self.client.get(reverse('api:search'), {'q': 'wren', 'type': 'users'})
        usernames = [u['username'] for u in response.data['results']['users']]
        self.assertEqual(usernames, ['writer'])
        self.assertNotIn('articles', response.data['results'])

    def test_limit_validation(self):
        response = self.client.get(reverse('api:search'), {'q': 'x', 'limit': 500})
        self.assertEqual(response.status_code, 400)


class StatsAndTrendingTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(email='t@example.com', username='trend', password='x')
        cls.hot = Article.objects.create(title='Hot', content='...', author=cls.author, status='published', views_count=50)
        cls.cold = Article.objects.create(title='Cold', content='...', author=cls.author, status='published', views_count=1)
        Article.objects.create(title='Draft', content='...', author=cls.author, status='draft')

    def setUp(self):
        cache.clear()

    def test_stats(self):
        response = self.client.get(reverse('api:api_stats'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['articles']['published'], 2)
        self.assertEqual(response.data['articles']['total'], 3)
        self.assertEqual(response.data['users']['total'], 1)

    def test_stats_cached(self):
        self.client.get(reverse('api:api_stats'))
        Article.objects.create(title='Later', content='...', author=self.author, status='published')
        response = self.client.get(reverse('api:api_stats'))
        self.assertEqual(response.data['articles']['published'], 2)

    def test_trending_orders_by_score(self):
        response = self.client.get(reverse('api:trending'))
        self.assertEqual(response.status_code, 200)
        titles = [a['title'] for a in response.data['trending_articles']]
        self.assertEqual(titles, ['Hot', 'Cold'])
        self.assertEqual(response.data['active_authors'][0]['username'], 'trend')


class DashboardTests(APITestCase):
    def test_requires_auth(self):
        response = self.client.get(reverse('api:user_dashboard'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['error']['code'], 'not_authenticated')

    def test_dashboard_counts(self):
        user = User.objects.create_user(email='d@example.com', username='dash', password='x')
        Article.objects.create(title='One', content='...', author=user, status='published', views_count=7)
        Article.objects.create(title='Two', content='...', author=user, status='draft')
        self.client.force_authenticate(user)
        response = self.client.get(reverse('api:user_dashboard'))
        self.assertEqual(response.status_code, 200)
        stats = response.data['stats']
        self.assertEqual(stats['published_articles'], 1)
        self.assertEqual(stats['draft_articles'], 1)
        self.assertEqual(stats['total_views'], 7)
        self.assertEqual(stats['followers'], 0)


class ThrottleTests(APITestCase):
    def test_staff_rate_parsed(self):
        from apps.api.throttling import CustomUserRateThrottle

        throttle = CustomUserRateThrottle()
        throttle.rate = throttle.STAFF_RATE
        num, duration = throttle.parse_rate(throttle.rate)
        self.assertEqual((num, duration), (5000, 3600))
