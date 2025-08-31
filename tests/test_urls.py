"""
File: tests/test_urls.py
URL resolution tests for all applications.
Tests URL patterns, view resolution, and routing configuration.
"""

from django.test import TestCase
from django.urls import reverse, resolve
from django.contrib.auth.models import User
from django.test.client import Client
from django.http import Http404

from accounts.views import UserProfileView, CustomLoginView
from core.views import HomeView
from notifications.views import NotificationListView


class URLResolutionTestCase(TestCase):
    """Test URL pattern resolution and reverse URL lookup."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_admin_urls(self):
        """Test admin URL resolution."""
        url = reverse('admin:index')
        self.assertEqual(url, '/admin/')
        
        resolver = resolve('/admin/')
        self.assertEqual(resolver.view_name, 'admin:index')
    
    def test_api_urls(self):
        """Test API URL resolution."""
        # Test API root
        url = reverse('api:api-root')
        self.assertEqual(url, '/api/')
        
        # Test API documentation
        url = reverse('api:schema-swagger-ui')
        self.assertIn('/api/docs/', url)
    
    def test_home_url(self):
        """Test home page URL resolution."""
        url = reverse('core:home')
        self.assertEqual(url, '/')
        
        resolver = resolve('/')
        self.assertEqual(resolver.func.view_class, HomeView)
    
    def test_accounts_urls(self):
        """Test accounts URL resolution."""
        # Login URL
        url = reverse('accounts:login')
        self.assertEqual(url, '/accounts/login/')
        
        resolver = resolve('/accounts/login/')
        self.assertEqual(resolver.func.view_class, CustomLoginView)
        
        # Profile URL
        url = reverse('accounts:profile', kwargs={'pk': self.user.pk})
        self.assertEqual(url, f'/accounts/profile/{self.user.pk}/')
        
        resolver = resolve(f'/accounts/profile/{self.user.pk}/')
        self.assertEqual(resolver.func.view_class, UserProfileView)
        
        # Registration URL
        url = reverse('accounts:register')
        self.assertEqual(url, '/accounts/register/')
        
        # Logout URL
        url = reverse('accounts:logout')
        self.assertEqual(url, '/accounts/logout/')
    
    def test_notifications_urls(self):
        """Test notifications URL resolution."""
        url = reverse('notifications:list')
        self.assertEqual(url, '/notifications/')
        
        resolver = resolve('/notifications/')
        self.assertEqual(resolver.func.view_class, NotificationListView)
    
    def test_media_urls_in_debug(self):
        """Test media URL serving in debug mode."""
        # This would be tested with DEBUG=True
        with self.settings(DEBUG=True):
            response = self.client.get('/media/test.jpg')
            # Should return 404 for non-existent files, not 500
            self.assertEqual(response.status_code, 404)
    
    def test_static_urls_in_debug(self):
        """Test static URL serving in debug mode."""
        with self.settings(DEBUG=True):
            response = self.client.get('/static/css/test.css')
            # Should return 404 for non-existent files, not 500
            self.assertEqual(response.status_code, 404)


class URLParameterTestCase(TestCase):
    """Test URL parameters and dynamic routing."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_user_profile_url_parameters(self):
        """Test user profile URL with parameters."""
        url = reverse('accounts:profile', kwargs={'pk': 999})
        resolver = resolve(url)
        self.assertEqual(resolver.kwargs['pk'], '999')
    
    def test_api_url_parameters(self):
        """Test API URL parameters."""
        # Test user detail API endpoint
        url = reverse('api:user-detail', kwargs={'pk': self.user.pk})
        resolver = resolve(url)
        self.assertEqual(resolver.kwargs['pk'], str(self.user.pk))


class URLNamespaceTestCase(TestCase):
    """Test URL namespacing and organization."""
    
    def test_app_namespaces(self):
        """Test that all apps use proper namespacing."""
        namespaces = [
            'core',
            'accounts', 
            'notifications',
            'api',
            'admin'
        ]
        
        for namespace in namespaces:
            try:
                # Try to reverse a URL in each namespace
                if namespace == 'core':
                    reverse(f'{namespace}:home')
                elif namespace == 'accounts':
                    reverse(f'{namespace}:login')
                elif namespace == 'notifications':
                    reverse(f'{namespace}:list')
                elif namespace == 'api':
                    reverse(f'{namespace}:api-root')
                elif namespace == 'admin':
                    reverse(f'{namespace}:index')
            except Exception as e:
                self.fail(f"Namespace {namespace} not properly configured: {e}")


class URLSecurityTestCase(TestCase):
    """Test URL security and access control."""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_admin_requires_authentication(self):
        """Test that admin URLs require authentication."""
        response = self.client.get('/admin/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)
    
    def test_protected_views_redirect(self):
        """Test that protected views redirect unauthenticated users."""
        protected_urls = [
            reverse('accounts:profile', kwargs={'pk': self.user.pk}),
            reverse('notifications:list'),
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            # Should redirect to login or return 403
            self.assertIn(response.status_code, [302, 403])


class URLPerformanceTestCase(TestCase):
    """Test URL resolution performance."""
    
    def test_url_resolution_performance(self):
        """Test that URL resolution is performant."""
        import time
        
        urls_to_test = [
            '/',
            '/accounts/login/',
            '/api/',
            '/admin/',
        ]
        
        for url in urls_to_test:
            start_time = time.time()
            try:
                resolve(url)
            except Http404:
                pass  # Some URLs might not exist, that's OK
            end_time = time.time()
            
            resolution_time = end_time - start_time
            # URL resolution should be very fast
            self.assertLess(resolution_time, 0.01, 
                           f"URL resolution for {url} took {resolution_time}s")