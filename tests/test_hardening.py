# File: DjangoVerseHub/tests/test_hardening.py
"""Security headers, metrics endpoint and conditional GET."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.articles.models import Article
from apps.comments.models import Comment

User = get_user_model()


class SecurityHeadersTests(TestCase):
    def test_csp_allows_the_cdns_the_templates_use(self):
        response = self.client.get(reverse("core:faq"))
        csp = response["Content-Security-Policy"]
        self.assertIn("script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("base-uri 'self'", csp)
        self.assertIn("https://fonts.gstatic.com", csp)

    def test_other_headers(self):
        response = self.client.get(reverse("core:faq"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertIn("camera=()", response["Permissions-Policy"])
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")
        self.assertNotIn("X-XSS-Protection", response)

    @override_settings(CSP_REPORT_ONLY=True, CSP_REPORT_URI="/csp-report/")
    def test_report_only_mode(self):
        response = self.client.get(reverse("core:faq"))
        self.assertNotIn("Content-Security-Policy", response)
        self.assertIn("report-uri /csp-report/", response["Content-Security-Policy-Report-Only"])

    @override_settings(CSP_ENABLED=False)
    def test_csp_can_be_disabled(self):
        response = self.client.get(reverse("core:faq"))
        self.assertNotIn("Content-Security-Policy", response)


class MetricsEndpointTests(TestCase):
    def test_anonymous_forbidden(self):
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 403)

    def test_staff_allowed(self):
        staff = User.objects.create_user(email="s@example.com", username="s", password="x", is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("metrics"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("django_http_requests_total", body)
        self.assertIn("djangoversehub_users_registered_total", body)

    @override_settings(METRICS_TOKEN="secret-token")
    def test_bearer_token(self):
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 403)
        self.assertEqual(self.client.get(reverse("metrics"), HTTP_AUTHORIZATION="Bearer wrong").status_code, 403)
        self.assertEqual(self.client.get(reverse("metrics"), HTTP_AUTHORIZATION="Bearer secret-token").status_code, 200)

    def test_domain_counters_increment(self):
        from django_verse_hub import metrics

        before_users = metrics.users_registered_total._value.get()
        before_articles = metrics.articles_published_total._value.get()
        before_comments = metrics.comments_created_total._value.get()
        user = User.objects.create_user(email="c@example.com", username="c", password="x")
        article = Article.objects.create(title="Draft", content="x", author=user, status="draft")
        self.assertEqual(metrics.articles_published_total._value.get(), before_articles)
        article.status = "published"
        article.save()
        article.save()  # re-saving a published article must not count again
        Comment.objects.create(content_object=article, author=user, content="hi")
        self.assertEqual(metrics.users_registered_total._value.get(), before_users + 1)
        self.assertEqual(metrics.articles_published_total._value.get(), before_articles + 1)
        self.assertEqual(metrics.comments_created_total._value.get(), before_comments + 1)


class ConditionalGetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="e@example.com", username="etag", password="x")
        self.article = Article.objects.create(title="Cached", content="body", author=self.user, status="published")

    def test_etag_roundtrip_for_anonymous(self):
        first = self.client.get(self.article.get_absolute_url())
        self.assertEqual(first.status_code, 200)
        etag = first["ETag"]
        self.assertTrue(etag.startswith('W/"'))
        again = self.client.get(self.article.get_absolute_url(), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(again.status_code, 304)

    def test_etag_changes_when_comment_added(self):
        etag = self.client.get(self.article.get_absolute_url())["ETag"]
        Comment.objects.create(content_object=self.article, author=self.user, content="new")
        response = self.client.get(self.article.get_absolute_url(), HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response["ETag"], etag)

    def test_no_etag_for_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("ETag", response)
