# File: DjangoVerseHub/apps/articles/tests/test_feeds.py

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.articles.models import Article, Category, Tag

User = get_user_model()


class FeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user(email="f@example.com", username="feeder", password="x", first_name="Fay")
        cls.category = Category.objects.create(name="Feeds", slug="feeds")
        cls.tag = Tag.objects.create(name="rss", slug="rss")
        cls.article = Article.objects.create(
            title="Feed me",
            content="**bold** body",
            summary="A summary",
            author=cls.author,
            category=cls.category,
            status="published",
        )
        cls.article.tags.add(cls.tag)
        Article.objects.create(title="Secret draft", content="x", author=cls.author, status="draft")

    def test_rss_feed(self):
        response = self.client.get(reverse("articles:feed"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/rss+xml", response["Content-Type"])
        body = response.content.decode()
        self.assertIn("Feed me", body)
        self.assertNotIn("Secret draft", body)
        self.assertIn("<p>A summary</p>", body.replace("&lt;", "<").replace("&gt;", ">"))
        self.assertIn("<category>Feeds</category>", body)

    def test_atom_feed(self):
        response = self.client.get(reverse("articles:feed_atom"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/atom+xml", response["Content-Type"])
        self.assertIn(b"Feed me", response.content)

    def test_scoped_feeds(self):
        for name, kwargs in [
            ("articles:feed_category", {"slug": "feeds"}),
            ("articles:feed_tag", {"slug": "rss"}),
            ("articles:feed_author", {"username": "feeder"}),
        ]:
            with self.subTest(feed=name):
                response = self.client.get(reverse(name, kwargs=kwargs))
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"Feed me", response.content)

    def test_scoped_feed_404(self):
        self.assertEqual(self.client.get(reverse("articles:feed_tag", kwargs={"slug": "nope"})).status_code, 404)

    def test_feed_links_in_head(self):
        response = self.client.get(reverse("core:home"))
        self.assertContains(response, 'type="application/rss+xml"')


class JsonLdTests(TestCase):
    def test_article_page_has_structured_data(self):
        author = User.objects.create_user(email="j@example.com", username="jsonld", password="x")
        article = Article.objects.create(title="Structured", content="Body text", author=author, status="published")
        response = self.client.get(article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        start = body.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        end = body.index("</script>", start)
        data = json.loads(body[start:end])
        self.assertEqual(data["@type"], "BlogPosting")
        self.assertEqual(data["headline"], "Structured")
        self.assertTrue(data["url"].startswith("http://testserver/articles/"))
        self.assertEqual(data["author"]["name"], "jsonld")

    def test_markdown_rendered_on_detail(self):
        author = User.objects.create_user(email="m@example.com", username="md", password="x")
        article = Article.objects.create(
            title="MD",
            content="## Section\n\n```python\nx = 1\n```\n\n<script>bad()</script>",
            author=author,
            status="published",
        )
        response = self.client.get(article.get_absolute_url())
        self.assertContains(response, "<h2")
        self.assertContains(response, 'class="language-python"')
        self.assertNotContains(response, "<script>bad()")
