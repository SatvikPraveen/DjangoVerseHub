"""
File: tests/test_performance.py
Performance and query-efficiency tests for DjangoVerseHub.
Tests N+1 query usage, caching, and response times for critical views.
"""

import time
from django.test import TestCase
from django.test.client import Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import connection, reset_queries
from django.test.utils import override_settings

from apps.notifications.models import Notification

User = get_user_model()


@override_settings(DEBUG=True)  # enables connection.queries tracking
class DatabasePerformanceTestCase(TestCase):
    """Test that critical views avoid N+1 queries."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='perf@example.com', password='testpass123', username='perfuser'
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_notification_list_query_efficiency(self):
        """Notification list should not issue one query per notification."""
        for i in range(10):
            Notification.objects.create(
                recipient=self.user,
                notification_type='comment',
                message=f'Notification {i}',
            )

        reset_queries()
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        query_count = len(connection.queries)
        # A well-optimised view should not need more than ~5 queries
        self.assertLessEqual(
            query_count, 10,
            f'Notification list issued {query_count} queries (possible N+1)'
        )

    def test_api_root_response(self):
        """API root endpoint should respond with 200."""
        response = self.client.get(reverse('api:api_root'))
        self.assertIn(response.status_code, [200, 301, 302])


class ResponseTimeTestCase(TestCase):
    """Smoke-test that critical pages respond within a generous time budget."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='time@example.com', password='testpass123', username='timeuser'
        )
        self.client = Client()
        self.client.force_login(self.user)

    def _response_time(self, url):
        start = time.monotonic()
        response = self.client.get(url)
        return time.monotonic() - start, response

    def test_home_page_response_time(self):
        """Home page should respond within 2 seconds."""
        elapsed, response = self._response_time(reverse('home'))
        self.assertIn(response.status_code, [200, 301, 302])
        self.assertLess(elapsed, 2.0, f'Home page took {elapsed:.2f}s')

    def test_notifications_list_response_time(self):
        """Notifications list should respond within 2 seconds."""
        elapsed, response = self._response_time(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed, 2.0, f'Notifications list took {elapsed:.2f}s')


import time
from django.test import TestCase, TransactionTestCase
from django.test.client import Client
