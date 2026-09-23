# File: DjangoVerseHub/apps/core/tests/test_views.py

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.articles.models import Article, Category, Tag
from apps.core.models import ContactMessage, NewsletterSubscriber, SiteSetting

User = get_user_model()


class HomeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='a@example.com', username='author', password='x')
        cls.category = Category.objects.create(name='Django', slug='django')
        cls.tag = Tag.objects.create(name='orm', slug='orm')
        cls.article = Article.objects.create(
            title='Hello', content='word ' * 300, author=cls.user, category=cls.category,
            status='published', is_featured=True,
        )
        cls.article.tags.add(cls.tag)
        Article.objects.create(title='Draft', content='secret', author=cls.user, status='draft')

    def test_home_renders_published_only(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello')
        self.assertNotContains(response, 'secret')
        self.assertEqual(response.context['stats']['articles'], 1)

    def test_home_shows_categories_and_tags(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'Django')
        self.assertContains(response, '#orm')

    def test_home_url_is_root(self):
        self.assertEqual(reverse('core:home'), '/')


class SearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='s@example.com', username='searcher', password='x', first_name='Ada')
        Article.objects.create(title='Celery tips', content='queues', author=cls.user, status='published')
        Article.objects.create(title='Hidden celery', content='draft', author=cls.user, status='draft')
        Tag.objects.create(name='celery', slug='celery')

    def test_empty_query(self):
        response = self.client.get(reverse('core:search'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_results'], 0)

    def test_search_all_scopes(self):
        response = self.client.get(reverse('core:search'), {'q': 'celery'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Celery tips')
        self.assertNotContains(response, 'Hidden celery')
        self.assertContains(response, '#celery')
        self.assertEqual(response.context['total_results'], 2)

    def test_search_people_scope(self):
        response = self.client.get(reverse('core:search'), {'q': 'ada', 'scope': 'people'})
        self.assertContains(response, '@searcher')
        self.assertIsNone(response.context['articles_page'])

    def test_invalid_scope_falls_back(self):
        response = self.client.get(reverse('core:search'), {'q': 'x', 'scope': 'nope'})
        self.assertEqual(response.context['scope'], 'all')


class StaticPagesTests(TestCase):
    def test_pages_render(self):
        for name in ['getting-started', 'guidelines', 'faq', 'api', 'privacy', 'terms', 'cookies']:
            with self.subTest(page=name):
                response = self.client.get(reverse(f'core:{name}'))
                self.assertEqual(response.status_code, 200)

    def test_robots_and_sitemap(self):
        robots = self.client.get(reverse('core:robots'))
        self.assertEqual(robots.status_code, 200)
        self.assertIn(b'Sitemap:', robots.content)
        sitemap = self.client.get(reverse('core:sitemap'))
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(b'<urlset', sitemap.content)


class ContactAndFeedbackTests(TestCase):
    def test_contact_get(self):
        self.assertEqual(self.client.get(reverse('core:contact')).status_code, 200)

    def test_contact_post_creates_message(self):
        response = self.client.post(reverse('core:contact'), {
            'name': 'Sam', 'email': 'sam@example.com', 'subject': 'Hi', 'message': 'This is a real message.',
        })
        self.assertRedirects(response, reverse('core:home'))
        message = ContactMessage.objects.get()
        self.assertEqual(message.kind, ContactMessage.Kind.CONTACT)
        self.assertEqual(message.status, ContactMessage.Status.NEW)

    def test_feedback_post_sets_kind(self):
        self.client.post(reverse('core:feedback'), {
            'name': 'Sam', 'email': 'sam@example.com', 'subject': 'Idea', 'message': 'Dark mode everywhere please.',
        })
        self.assertEqual(ContactMessage.objects.get().kind, ContactMessage.Kind.FEEDBACK)

    def test_honeypot_blocks_bots(self):
        response = self.client.post(reverse('core:contact'), {
            'name': 'Bot', 'email': 'bot@example.com', 'subject': 'Buy', 'message': 'cheap stuff for you',
            'website_url': 'http://spam.example',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_short_message_rejected(self):
        response = self.client.post(reverse('core:contact'), {
            'name': 'Sam', 'email': 'sam@example.com', 'subject': 'Hi', 'message': 'short',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'message', 'Please provide a little more detail (at least 10 characters).')

    def test_authenticated_user_attached(self):
        user = User.objects.create_user(email='u@example.com', username='u', password='x')
        self.client.force_login(user)
        self.client.post(reverse('core:contact'), {
            'name': 'U', 'email': 'u@example.com', 'subject': 'Hi', 'message': 'Attached to my account.',
        })
        self.assertEqual(ContactMessage.objects.get().user, user)


class NewsletterTests(TestCase):
    def test_subscribe_sends_confirmation(self):
        response = self.client.post(reverse('core:newsletter_signup'), {'email': 'New@Example.com'})
        self.assertEqual(response.status_code, 302)
        subscriber = NewsletterSubscriber.objects.get()
        self.assertEqual(subscriber.email, 'new@example.com')
        self.assertFalse(subscriber.is_confirmed)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(subscriber.confirmation_token, mail.outbox[0].body)

    def test_subscribe_json(self):
        response = self.client.post(
            reverse('core:newsletter_signup'), {'email': 'json@example.com'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(response.json()['created'])

    def test_subscribe_invalid_json(self):
        response = self.client.post(
            reverse('core:newsletter_signup'), {'email': 'nope'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 400)

    def test_confirm_and_unsubscribe(self):
        subscriber = NewsletterSubscriber.objects.create(email='c@example.com')
        self.client.get(reverse('core:newsletter_confirm', args=[subscriber.confirmation_token]))
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)

        page = self.client.get(reverse('core:newsletter_unsubscribe', args=[subscriber.confirmation_token]))
        self.assertEqual(page.status_code, 200)
        self.client.post(reverse('core:newsletter_unsubscribe', args=[subscriber.confirmation_token]))
        subscriber.refresh_from_db()
        self.assertFalse(subscriber.is_active)

    def test_resubscribe_reactivates(self):
        subscriber = NewsletterSubscriber.objects.create(email='r@example.com')
        subscriber.confirm()
        subscriber.unsubscribe()
        self.client.post(reverse('core:newsletter_signup'), {'email': 'r@example.com'})
        subscriber.refresh_from_db()
        self.assertTrue(subscriber.is_active)
        self.assertEqual(len(mail.outbox), 0)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse('core:newsletter_signup')).status_code, 405)


class ContextProcessorTests(TestCase):
    def test_public_site_settings_exposed(self):
        SiteSetting.objects.create(key='banner', value='Hello!', is_public=True)
        SiteSetting.objects.create(key='secret', value='hidden', is_public=False)
        response = self.client.get(reverse('core:faq'))
        settings = response.context['site_settings']
        self.assertEqual(settings['banner'], 'Hello!')
        self.assertNotIn('secret', settings)

    def test_notification_context_for_anonymous(self):
        response = self.client.get(reverse('core:faq'))
        self.assertEqual(response.context['unread_notifications_count'], 0)

    def test_notification_context_for_user(self):
        from apps.notifications.models import Notification

        user = User.objects.create_user(email='n@example.com', username='n', password='x')
        other = User.objects.create_user(email='o@example.com', username='o', password='x')
        Notification.objects.create(recipient=user, sender=other, notification_type='comment', message='hi')
        self.client.force_login(user)
        response = self.client.get(reverse('core:faq'))
        self.assertEqual(response.context['unread_notifications_count'], 1)
        self.assertEqual(len(response.context['recent_notifications']), 1)
