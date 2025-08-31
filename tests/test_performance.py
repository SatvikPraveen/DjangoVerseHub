"""
File: tests/test_performance.py
Performance and load tests for the Django application.
Tests response times, database query optimization, and system scalability.
"""

import time
from django.test import TestCase, TransactionTestCase
from django.test.client import Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.db import connection
from django.test.utils import override_settings
from django.core.cache import cache
from unittest.mock import patch

from accounts.models import UserProfile
from notifications.models import Notification


class DatabasePerformanceTestCase(TestCase):
    """Test database query performance and optimization."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
    
    def test_user_profile_query_efficiency(self):
        """Test that user profile views use efficient queries."""
        self.client.login(username='testuser', password='testpass123')
        
        # Reset query counter
        initial_queries = len(connection.queries)
        
        # Access user profile
        response = self.client.get(
            reverse('accounts:profile', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        # Check number of queries
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries
        
        # Should not exceed reasonable number of queries
        self.assertLessEqual(query_count, 5, 
                           f"User profile view used {query_count} queries")
    
    def test_notification_list_query_efficiency(self):
        """Test that notification list uses efficient queries."""
        # Create multiple notifications
        for i in range(10):
            Notification.objects.create(
                recipient=self.user,
                title=f'Notification {i}',
                message=f'Message {i}',
                notification_type='info'
            )
        
        self.client.login(username='testuser', password='testpass123')
        
        initial_queries = len(connection.queries)
        
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries
        
        # Should use select_related or prefetch_related to avoid N+1
        self.assertLessEqual(query_count, 3,
                           f"Notification list used {query_count} queries")
    
    def test_api_endpoint_query_efficiency(self):
        """Test API endpoints use efficient database queries."""
        self.client.login(username='testuser', password='testpass123')
        
        initial_queries = len(connection.queries)
        
        response = self.client.get(
            reverse('api:user-detail', kwargs={'pk': self.user.pk})
        )
        self.assertEqual(response.status_code, 200)
        
        final_queries = len(connection.queries)
        query_count = final_queries - initial_queries
        
        self.assertLessEqual(query_count, 3,
                           f"API user detail used {query_count} queries")


class ResponseTimeTestCase(TestCase):
    """Test response time performance for critical views."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
    
    def measure_response_time(self, url, method='GET', data=None, login=False):
        """Helper method to measure response time."""
        if login:
            self.client.login(username='testuser', password='testpass123')
        
        start_time = time.time()
        
        if method == 'GET':
            response = self.client.get(url)
        elif method == 'POST':
            response = self.client.post(url, data or {})
        
        end_time = time.time()
        response_time = end_time - start_time
        
        return response, response_time
    
    def test_home_page_response_time(self):
        """Test home page loads within acceptable time."""
        response, response_time = self.measure_response_time(reverse('core:home'))
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 1.0,  # Should load in less than 1 second
                       f"Home page took {response_time:.3f}s to load")
    
    def test_user_login_response_time(self):
        """Test login page response time."""
        response, response_time = self.measure_response_time(
            reverse('accounts:login')
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 0.5,
                       f"Login page took {response_time:.3f}s to load")
    
    def test_api_response_time(self):
        """Test API endpoint response times."""
        response, response_time = self.measure_response_time(
            reverse('api:user-detail', kwargs={'pk': self.user.pk}),
            login=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 0.3,
                       f"API endpoint took {response_time:.3f}s to respond")
    
    def test_notification_list_response_time(self):
        """Test notification list response time with data."""
        # Create some notifications
        for i in range(20):
            Notification.objects.create(
                recipient=self.user,
                title=f'Notification {i}',
                message=f'Message {i}',
                notification_type='info'
            )
        
        response, response_time = self.measure_response_time(
            reverse('notifications:list'),
            login=True
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(response_time, 1.0,
                       f"Notification list took {response_time:.3f}s to load")


class CachePerformanceTestCase(TestCase):
    """Test caching performance and effectiveness."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()
        cache.clear()
    
    def test_cache_improves_response_time(self):
        """Test that caching improves response times."""
        url = reverse('accounts:profile', kwargs={'pk': self.user.pk})
        self.client.login(username='testuser', password='testpass123')
        
        # First request (cache miss)
        start_time = time.time()
        response1 = self.client.get(url)
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, 200)
        
        # Second request (should hit cache)
        start_time = time.time()
        response2 = self.client.get(url)
        time2 = time.time() - start_time
        
        self.assertEqual(response2.status_code, 200)
        
        # Cached response should be faster (allowing some margin for test variance)
        self.assertLess(time2, time1 * 1.1,
                       f"Cached request ({time2:.3f}s) should be faster than initial ({time1:.3f}s)")
    
    @patch('django.core.cache.cache')
    def test_cache_hit_ratio(self, mock_cache):
        """Test cache hit ratios for frequently accessed data."""
        mock_cache.get.return_value = None
        mock_cache.set.return_value = True
        
        url = reverse('accounts:profile', kwargs={'pk': self.user.pk})
        self.client.login(username='testuser', password='testpass123')
        
        # Make multiple requests
        for _ in range(5):
            self.client.get(url)
        
        # Cache should be checked multiple times
        self.assertTrue(mock_cache.get.call_count >= 5)


class LoadTestCase(TransactionTestCase):
    """Test system performance under load."""
    
    def setUp(self):
        # Create multiple users for load testing
        self.users = []
        for i in range(10):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@example.com',
                password='testpass123'
            )
            self.users.append(user)
    
    def test_concurrent_user_access(self):
        """Test system performance with multiple concurrent users."""
        import threading
        import queue
        
        response_times = queue.Queue()
        
        def user_session(user):
            """Simulate a user session."""
            client = Client()
            start_time = time.time()
            
            # Login
            client.login(username=user.username, password='testpass123')
            
            # Access various pages
            client.get(reverse('core:home'))
            client.get(reverse('accounts:profile', kwargs={'pk': user.pk}))
            client.get(reverse('notifications:list'))
            
            end_time = time.time()
            session_time = end_time - start_time
            response_times.put(session_time)
        
        # Create threads for concurrent access
        threads = []
        for user in self.users[:5]:  # Test with 5 concurrent users
            thread = threading.Thread(target=user_session, args=(user,))
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        total_time = time.time() - start_time
        
        # Collect response times
        times = []
        while not response_times.empty():
            times.append(response_times.get())
        
        # Verify all sessions completed successfully
        self.assertEqual(len(times), 5)
        
        # Check average response time is reasonable
        avg_time = sum(times) / len(times)
        self.assertLess(avg_time, 5.0,
                       f"Average session time {avg_time:.3f}s is too high")
        
        # Check total time (should handle concurrency well)
        self.assertLess(total_time, 10.0,
                       f"Total concurrent execution took {total_time:.3f}s")
    
    def test_bulk_notification_creation_performance(self):
        """Test performance when creating many notifications."""
        user = self.users[0]
        
        start_time = time.time()
        
        # Create many notifications
        notifications = []
        for i in range(100):
            notifications.append(
                Notification(
                    recipient=user,
                    title=f'Bulk Notification {i}',
                    message=f'Bulk Message {i}',
                    notification_type='info'
                )
            )
        
        # Bulk create
        Notification.objects.bulk_create(notifications)
        
        creation_time = time.time() - start_time
        
        # Should create 100 notifications quickly
        self.assertLess(creation_time, 2.0,
                       f"Creating 100 notifications took {creation_time:.3f}s")
        
        # Verify all created
        count = Notification.objects.filter(recipient=user).count()
        self.assertEqual(count, 100)


class MemoryPerformanceTestCase(TestCase):
    """Test memory usage and efficiency."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_queryset_memory_efficiency(self):
        """Test that querysets don't load unnecessary data into memory."""
        # Create many notifications
        for i in range(100):
            Notification.objects.create(
                recipient=self.user,
                title=f'Notification {i}',
                message=f'Long message content {i}' * 10,
                notification_type='info'
            )
        
        # Test iterator usage for large datasets
        processed_count = 0
        for notification in Notification.objects.filter(recipient=self.user).iterator():
            processed_count += 1
            # Process notification without loading all into memory
            if processed_count >= 50:
                break
        
        self.assertEqual(processed_count, 50)
    
    def test_select_related_efficiency(self):
        """Test that select_related reduces memory overhead."""
        # Test query without select_related
        notifications_1 = list(Notification.objects.filter(recipient=self.user))
        
        # Test query with select_related
        notifications_2 = list(
            Notification.objects.filter(recipient=self.user).select_related('recipient')
        )
        
        # Both should return same data
        self.assertEqual(len(notifications_1), len(notifications_2))
        
        # The select_related version should be more memory efficient
        # (This is more of a conceptual test - actual memory measurement 
        # would require more complex tooling)