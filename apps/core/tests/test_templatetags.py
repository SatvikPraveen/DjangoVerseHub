# File: DjangoVerseHub/apps/core/tests/test_templatetags.py

from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase


class UpdateQueryTagTests(SimpleTestCase):
    def render(self, tag, query=''):
        request = RequestFactory().get('/?' + query)
        return Template('{% load core_tags %}' + tag).render(Context({'request': request}))

    def test_adds_and_preserves(self):
        out = self.render('{% update_query page=2 %}', 'q=django&sort=new')
        self.assertIn('q=django', out)
        self.assertIn('page=2', out)
        self.assertFalse(out.startswith('?'))

    def test_replaces_existing(self):
        out = self.render('{% update_query page=3 %}', 'page=1')
        self.assertEqual(out, 'page=3')

    def test_removes_with_none(self):
        out = self.render('{% update_query page=None %}', 'page=1&q=x')
        self.assertEqual(out, 'q=x')

    def test_no_request(self):
        out = Template('{% load core_tags %}{% update_query page=1 %}').render(Context({}))
        self.assertEqual(out, '')


class FilterTests(SimpleTestCase):
    def test_humanize_count(self):
        from apps.core.templatetags.core_tags import humanize_count

        self.assertEqual(humanize_count(999), '999')
        self.assertEqual(humanize_count(1200), '1.2K')
        self.assertEqual(humanize_count(1000), '1K')
        self.assertEqual(humanize_count(2_500_000), '2.5M')
        self.assertEqual(humanize_count('x'), 'x')

    def test_initials(self):
        from types import SimpleNamespace

        from apps.core.templatetags.core_tags import initials

        self.assertEqual(initials(SimpleNamespace(get_full_name=lambda: 'Ada Lovelace', username='ada')), 'AL')
        self.assertEqual(initials(SimpleNamespace(get_full_name=lambda: '', username='grace')), 'GR')
        self.assertEqual(initials(None), '?')
