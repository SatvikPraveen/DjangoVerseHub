"""
File: tests/test_urls.py
URL resolution tests for all applications.
Tests URL patterns, view resolution, and routing configuration.
"""

from django.test import TestCase
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from django.test.client import Client

from apps.notifications.views import NotificationListView

User = get_user_model()


class URLResolutionTestCase(TestCase):
    """Test URL pattern resolution and reverse URL lookup."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='urltest@example.com',
            password='testpass123',
            username='urltestuser',
        )

    # ------------------------------------------------------------------ admin
    def test_admin_url(self):
        url = reverse('admin:index')
        self.assertEqual(url, '/admin/')
        self.assertEqual(resolve('/admin/').view_name, 'admin:index')

    # ------------------------------------------------------------------- home
    def test_home_url(self):
        url = reverse('home')
        self.assertEqual(url, '/')

    # ---------------------------------------------------------------- api
    def test_api_root_url(self):
        url = reverse('api:api_root')
        self.assertIn('/api/v1/', url)

    def test_api_swagger_url(self):
        url = reverse('api:schema_swagger_ui')
        self.assertIn('/api/v1/docs/', url)

    # --------------------------------------------------------------- users
    def test_users_signup_url(self):
        url = reverse('users:signup')
        self.assertEqual(url, '/users/signup/')

    def test_users_login_url(self):
        url = reverse('users:login')
        self.assertEqual(url, '/users/login/')

    def test_users_logout_url(self):
        url = reverse('users:logout')
        self.assertEqual(url, '/users/logout/')

    def test_users_profile_url(self):
        url = reverse('users:profile', kwargs={'pk': self.user.pk})
        self.assertIn(str(self.user.pk), url)

    # ---------------------------------------------------------- notifications
    def test_notifications_list_url(self):
        url = reverse('notifications:list')
        self.assertEqual(url, '/notifications/')
        self.assertEqual(resolve('/notifications/').func.view_class, NotificationListView)

    # ------------------------------------------------------ articles
    def test_articles_list_url(self):
        url = reverse('articles:list')
        self.assertEqual(url, '/articles/')

    def test_articles_category_list_url(self):
        url = reverse('articles:category_list')
        self.assertEqual(url, '/articles/categories/')

    def test_articles_category_detail_url(self):
        url = reverse('articles:category_detail', kwargs={'slug': 'python'})
        self.assertEqual(url, '/articles/category/python/')

    def test_articles_tags_url(self):
        url = reverse('articles:tags')
        self.assertEqual(url, '/articles/tags/')

    def test_articles_tag_detail_url(self):
        url = reverse('articles:tag_detail', kwargs={'slug': 'django'})
        self.assertEqual(url, '/articles/tag/django/')

    # ----------------------------------------------------- static / media 404s
    def test_missing_static_returns_404_not_500(self):
        with self.settings(DEBUG=True):
            response = self.client.get('/static/css/does-not-exist.css')
            self.assertEqual(response.status_code, 404)

    def test_missing_media_returns_404_not_500(self):
        with self.settings(DEBUG=True):
            response = self.client.get('/media/does-not-exist.jpg')
            self.assertEqual(response.status_code, 404)


from django.test import TestCase
from django.urls import reverse, resolve
