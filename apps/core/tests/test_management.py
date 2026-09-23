# File: DjangoVerseHub/apps/core/tests/test_management.py

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.articles.models import Article, ArticleLike, Bookmark
from apps.comments.models import Comment
from apps.notifications.models import Notification
from apps.users.models import Follow

User = get_user_model()


class GenerateDemoDataTests(TestCase):
    def test_generates_interlinked_data(self):
        out = StringIO()
        call_command("generate_demo_data", users=6, articles=12, comments=20, seed=1, admin=True, stdout=out)
        self.assertEqual(User.objects.count(), 7)
        self.assertTrue(User.objects.filter(is_superuser=True).exists())
        self.assertEqual(Article.objects.count(), 12)
        self.assertEqual(Comment.objects.count(), 20)
        self.assertGreater(Follow.objects.count(), 0)
        self.assertGreater(ArticleLike.objects.count() + Bookmark.objects.count(), 0)
        # Notifications come from the real signal handlers
        self.assertGreater(Notification.objects.count(), 0)
        self.assertIn("Demo data ready", out.getvalue())

    def test_clear_removes_only_demo_users(self):
        real = User.objects.create_user(email="real@example.com", username="real", password="x")
        call_command("generate_demo_data", users=3, articles=3, comments=2, seed=2, stdout=StringIO())
        call_command("generate_demo_data", users=2, articles=2, comments=2, seed=3, clear=True, stdout=StringIO())
        self.assertTrue(User.objects.filter(pk=real.pk).exists())
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(Article.objects.count(), 2)

    def test_seed_is_reproducible(self):
        call_command("generate_demo_data", users=4, articles=4, comments=3, seed=7, stdout=StringIO())
        first = sorted(Article.objects.values_list("title", flat=True))
        call_command("generate_demo_data", users=4, articles=4, comments=3, seed=7, clear=True, stdout=StringIO())
        second = sorted(Article.objects.values_list("title", flat=True))
        self.assertEqual(first, second)
