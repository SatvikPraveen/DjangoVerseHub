# File: DjangoVerseHub/apps/core/tests/test_markdown.py

from django.template import Context, Template
from django.test import SimpleTestCase

from apps.core.markdown import markdown_to_text, render_markdown, sanitize_html


class RenderMarkdownTests(SimpleTestCase):
    def test_basic_formatting(self):
        html = render_markdown("# Title\n\nSome **bold** and `code`.", use_cache=False)
        self.assertIn("<h1", html)
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<code>code</code>", html)

    def test_fenced_code_keeps_language_class(self):
        html = render_markdown("```python\nprint(1)\n```", use_cache=False)
        self.assertIn('<code class="language-python">', html)

    def test_tables(self):
        html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |", use_cache=False)
        self.assertIn("<table>", html)

    def test_script_and_handlers_stripped(self):
        html = render_markdown(
            '<script>alert(1)</script><p onclick="x()">hi</p><a href="javascript:evil()">l</a>'
            '<img src="x" onerror="evil()">',
            use_cache=False,
        )
        self.assertNotIn("<script", html)
        self.assertNotIn("onclick", html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("javascript:", html)
        self.assertIn("hi", html)

    def test_links_get_rel(self):
        html = render_markdown("[site](https://example.com)", use_cache=False)
        self.assertIn('rel="nofollow noopener noreferrer"', html)
        self.assertIn('href="https://example.com"', html)

    def test_comment_profile_drops_headings_and_images(self):
        html = render_markdown(
            "# Heading\n\n![x](https://example.com/x.png)\n\ntext", profile="comment", use_cache=False
        )
        self.assertNotIn("<h1", html)
        self.assertNotIn("<img", html)
        self.assertIn("text", html)

    def test_arbitrary_classes_removed(self):
        html = sanitize_html('<code class="language-js evil">x</code><span class="evil">y</span>')
        self.assertIn('class="language-js"', html)
        self.assertNotIn("evil", html)

    def test_empty(self):
        self.assertEqual(render_markdown(""), "")
        self.assertEqual(render_markdown(None), "")

    def test_markdown_to_text(self):
        text = markdown_to_text("# Hello *world*\n\nMore text here.", limit=12)
        self.assertTrue(text.startswith("Hello world"))
        self.assertTrue(text.endswith("…"))

    def test_template_filters(self):
        out = Template(
            '{% load core_tags %}{{ body|markdown }}|{{ body|markdown:"comment" }}|{{ body|markdown_text }}'
        ).render(Context({"body": "## Hi <script>x</script>"}))
        first, second, third = out.split("|")
        self.assertIn("<h2", first)
        self.assertNotIn("<h2", second)
        self.assertNotIn("<script", out)
        self.assertEqual(third.strip(), "Hi")
