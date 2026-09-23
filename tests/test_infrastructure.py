# File: DjangoVerseHub/tests/test_infrastructure.py
"""Tests for project-level plumbing: health probes, request ids, API error envelope, docs."""

import logging
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from django_verse_hub.middleware import RequestIDFilter, get_request_id


class HealthEndpointTests(TestCase):
    def test_liveness(self):
        response = self.client.get(reverse('health_live'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_readiness_ok(self):
        response = self.client.get(reverse('health_ready'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['checks']['database']['status'], 'ok')
        self.assertEqual(data['checks']['cache']['status'], 'ok')
        self.assertEqual(data['checks']['celery']['status'], 'skipped')

    def test_readiness_reports_failure(self):
        with mock.patch('django_verse_hub.health._check_cache', side_effect=RuntimeError('redis down')):
            response = self.client.get(reverse('health_ready'))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['status'], 'degraded')
        self.assertEqual(response.json()['checks']['cache']['status'], 'error')

    def test_legacy_health_alias(self):
        self.assertEqual(self.client.get(reverse('health_check')).status_code, 200)

    def test_api_health_uses_probe(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('checks', response.json())
        self.assertIn('timestamp', response.json())

    def test_health_only_get(self):
        self.assertEqual(self.client.post(reverse('health_live')).status_code, 405)


class RequestIDMiddlewareTests(TestCase):
    def test_generates_request_id(self):
        response = self.client.get(reverse('health_live'))
        self.assertEqual(len(response['X-Request-ID']), 32)

    def test_echoes_upstream_request_id(self):
        response = self.client.get(reverse('health_live'), HTTP_X_REQUEST_ID='abc-123')
        self.assertEqual(response['X-Request-ID'], 'abc-123')

    def test_rejects_non_ascii_upstream_id(self):
        response = self.client.get(reverse('health_live'), HTTP_X_REQUEST_ID='ñ' * 10)
        self.assertNotEqual(response['X-Request-ID'], 'ñ' * 10)

    def test_context_is_reset_after_request(self):
        self.client.get(reverse('health_live'), HTTP_X_REQUEST_ID='leak-check')
        self.assertEqual(get_request_id(), '-')

    def test_logging_filter_adds_attribute(self):
        record = logging.LogRecord('x', logging.INFO, __file__, 1, 'msg', None, None)
        self.assertTrue(RequestIDFilter().filter(record))
        self.assertEqual(record.request_id, '-')


class APIErrorEnvelopeTests(TestCase):
    def test_unauthenticated_error_shape(self):
        response = Client().get('/api/v1/dashboard/')
        self.assertIn(response.status_code, (401, 403))
        body = response.json()
        self.assertIn('error', body)
        self.assertIn('code', body['error'])
        self.assertIn('message', body['error'])
        self.assertIn('request_id', body['error'])

    def test_not_found_error_shape(self):
        response = Client().get('/api/v1/articles/does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'not_found')


class APIDocsTests(TestCase):
    def test_schema_generates(self):
        response = self.client.get(reverse('api:schema'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'openapi', response.content)

    def test_swagger_and_redoc_pages(self):
        self.assertEqual(self.client.get(reverse('api:schema_swagger_ui')).status_code, 200)
        self.assertEqual(self.client.get(reverse('api:schema_redoc')).status_code, 200)


@override_settings(RATE_LIMIT_ENABLED=True, RATE_LIMIT_REQUESTS_PER_MINUTE=2, DEBUG=False)
class RateLimitMiddlewareTests(TestCase):
    def test_limit_enforced_with_retry_after(self):
        from django.core.cache import cache

        cache.clear()
        url = reverse('core:faq')
        self.assertEqual(self.client.get(url, REMOTE_ADDR='10.0.0.9').status_code, 200)
        self.assertEqual(self.client.get(url, REMOTE_ADDR='10.0.0.9').status_code, 200)
        blocked = self.client.get(url, REMOTE_ADDR='10.0.0.9')
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked['Retry-After'], '60')
        cache.clear()
