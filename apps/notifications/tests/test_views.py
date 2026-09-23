# File: DjangoVerseHub/apps/notifications/tests/test_views.py
from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.test import TestCase, override_settings
from django.test.client import Client
from django.urls import reverse
from rest_framework.test import APIClient

from apps.notifications.models import Notification, NotificationPreference

User = get_user_model()


class NotificationViewTestBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='me@test.com', password='testpass123', username='me')
        self.other = User.objects.create_user(email='other@test.com', password='testpass123', username='other')
        self.client = Client()
        self.client.force_login(self.user)

    def make(self, recipient=None, **kwargs):
        kwargs.setdefault('notification_type', 'system')
        kwargs.setdefault('message', 'Hello')
        return Notification.objects.create(recipient=recipient or self.user, **kwargs)


class NotificationListViewTest(NotificationViewTestBase):
    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_shows_only_own_notifications(self):
        self.make(message='mine')
        self.make(recipient=self.other, message='theirs')
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mine')
        self.assertNotContains(response, 'theirs')
        self.assertEqual(response.context['unread_notifications_count'], 1)

    def test_filters_by_status_and_type(self):
        read = self.make(message='already read', notification_type='like')
        read.mark_as_read()
        fresh = self.make(message='fresh comment', notification_type='comment', sender=self.other)

        def listed(response):
            # The navbar dropdown (base.html) also renders recent notifications,
            # so assert on the view's own queryset rather than the whole page.
            return [n.pk for n in response.context['notifications']]

        response = self.client.get(reverse('notifications:list'), {'status': 'unread'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(listed(response), [fresh.pk])
        self.assertEqual(response.context['current_status'], 'unread')

        response = self.client.get(reverse('notifications:list'), {'status': 'read'})
        self.assertEqual(listed(response), [read.pk])

        response = self.client.get(reverse('notifications:list'), {'type': 'like'})
        self.assertEqual(listed(response), [read.pk])
        self.assertEqual(response.context['current_type'], 'like')

        # Unknown filters are ignored, not 500s.
        response = self.client.get(reverse('notifications:list'), {'type': 'bogus', 'status': 'nope'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['notifications']), 2)

    def test_pagination_keeps_filters(self):
        for i in range(25):
            self.make(message=f'n{i}', notification_type='comment')
        response = self.client.get(reverse('notifications:list'), {'type': 'comment'})
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(len(response.context['notifications']), 20)
        self.assertContains(response, '?page=2&amp;type=comment')
        response = self.client.get(reverse('notifications:list'), {'type': 'comment', 'page': 2})
        self.assertEqual(len(response.context['notifications']), 5)

    @override_settings(DEBUG=True)
    def test_query_count_is_constant(self):
        for i in range(15):
            self.make(message=f'n{i}', notification_type='comment', sender=self.other)
        reset_queries()
        response = self.client.get(reverse('notifications:list'))
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(connection.queries), 10, [q['sql'] for q in connection.queries])

    def test_empty_state(self):
        response = self.client.get(reverse('notifications:list'))
        self.assertContains(response, 'No notifications yet')


class MarkAllReadWebViewTest(NotificationViewTestBase):
    def test_post_marks_all_and_redirects(self):
        self.make()
        self.make()
        self.make(recipient=self.other)
        response = self.client.post(reverse('notifications:mark_all_read'), {'next': '/notifications/?status=unread'})
        self.assertRedirects(response, '/notifications/?status=unread', fetch_redirect_response=False)
        self.assertEqual(Notification.objects.unread(self.user).count(), 0)
        self.assertEqual(Notification.objects.unread(self.other).count(), 1)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse('notifications:mark_all_read')).status_code, 405)

    def test_unsafe_next_is_ignored(self):
        response = self.client.post(reverse('notifications:mark_all_read'), {'next': 'https://evil.example/'})
        self.assertRedirects(response, reverse('notifications:list'), fetch_redirect_response=False)


class NotificationPreferenceViewTest(NotificationViewTestBase):
    def test_get_creates_defaults_and_renders(self):
        response = self.client.get(reverse('notifications:preferences'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notification preferences')
        self.assertTrue(NotificationPreference.objects.filter(user=self.user).exists())

    def test_post_saves(self):
        response = self.client.post(reverse('notifications:preferences'), {
            'in_app_comment': 'on', 'in_app_follow': 'on', 'in_app_mention': 'on', 'in_app_post': 'on',
            # in_app_like omitted -> False
            'email_comment': 'on',
            'digest_frequency': 'weekly',
        })
        self.assertRedirects(response, reverse('notifications:preferences'))
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertFalse(prefs.in_app_like)
        self.assertTrue(prefs.in_app_comment)
        self.assertTrue(prefs.email_comment)
        self.assertFalse(prefs.email_follow)
        self.assertEqual(prefs.digest_frequency, 'weekly')

    def test_invalid_digest_rejected(self):
        response = self.client.post(reverse('notifications:preferences'), {'digest_frequency': 'hourly'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('notifications:preferences')).status_code, 302)


class NotificationJSONAPITest(NotificationViewTestBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def test_list_api_scoped_to_user_with_unread_count(self):
        self.make(message='mine', sender=self.other)
        self.make(recipient=self.other, message='theirs')
        response = self.api.get(reverse('notifications:api_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['unread_count'], 1)
        item = response.data['results'][0]
        self.assertEqual(item['message'], 'mine')
        self.assertEqual(item['sender']['username'], 'other')
        self.assertIn('url', item)
        self.assertIn('icon', item)

    def test_list_api_filters(self):
        read = self.make(message='r', notification_type='like')
        read.mark_as_read()
        self.make(message='u', notification_type='comment')
        self.assertEqual(self.api.get(reverse('notifications:api_list'), {'unread': 'true'}).data['count'], 1)
        self.assertEqual(self.api.get(reverse('notifications:api_list'), {'status': 'read'}).data['count'], 1)
        self.assertEqual(self.api.get(reverse('notifications:api_list'), {'type': 'like'}).data['count'], 1)

    def test_list_api_requires_auth(self):
        self.assertIn(APIClient().get(reverse('notifications:api_list')).status_code, (401, 403))

    def test_mark_read(self):
        n = self.make()
        response = self.api.post(reverse('notifications:api_mark_read', kwargs={'notification_id': n.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['unread_count'], 0)
        n.refresh_from_db()
        self.assertTrue(n.is_read)

    def test_cannot_mark_or_delete_others_notifications(self):
        n = self.make(recipient=self.other)
        self.assertEqual(self.api.post(reverse('notifications:api_mark_read', kwargs={'notification_id': n.pk})).status_code, 404)
        self.assertEqual(self.api.delete(reverse('notifications:api_delete', kwargs={'notification_id': n.pk})).status_code, 404)
        n.refresh_from_db()
        self.assertFalse(n.is_read)
        self.assertTrue(Notification.objects.filter(pk=n.pk).exists())

    def test_mark_all_read_and_unread_count(self):
        self.make()
        self.make()
        self.assertEqual(self.api.get(reverse('notifications:api_unread_count')).data['unread_count'], 2)
        response = self.api.post(reverse('notifications:api_mark_all_read'))
        self.assertEqual(response.data['marked_count'], 2)
        self.assertEqual(self.api.get(reverse('notifications:api_unread_count')).data['unread_count'], 0)

    def test_delete(self):
        n = self.make()
        response = self.api.delete(reverse('notifications:api_delete', kwargs={'notification_id': n.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.filter(pk=n.pk).exists())

    def test_preferences_endpoint(self):
        url = reverse('notifications:api_preferences')
        self.assertEqual(self.api.get(url).data['digest_frequency'], 'daily')
        response = self.api.patch(url, {'digest_frequency': 'none', 'email_like': True}, format='json')
        self.assertEqual(response.status_code, 200)
        prefs = NotificationPreference.objects.get(user=self.user)
        self.assertEqual(prefs.digest_frequency, 'none')
        self.assertTrue(prefs.email_like)
        self.assertEqual(self.api.patch(url, {'digest_frequency': 'hourly'}, format='json').status_code, 400)


class NotificationViewSetTest(NotificationViewTestBase):
    """The router-registered ViewSet under /api/v1/notifications (router has trailing_slash=False)."""

    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    @staticmethod
    def detail(n, action='detail'):
        return reverse(f'api:notification-{action}', kwargs={'pk': n.pk})

    def test_list_and_detail_scoped(self):
        mine = self.make(message='mine')
        theirs = self.make(recipient=self.other, message='theirs')
        response = self.api.get(reverse('api:notification-list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(self.api.get(self.detail(mine)).status_code, 200)
        self.assertEqual(self.api.get(self.detail(theirs)).status_code, 404)

    def test_create_not_allowed(self):
        response = self.api.post(
            reverse('api:notification-list'),
            {'recipient': str(self.user.pk), 'notification_type': 'system', 'message': 'x'},
        )
        self.assertEqual(response.status_code, 405)

    def test_patch_only_is_read(self):
        n = self.make()
        response = self.api.patch(self.detail(n), {'is_read': True}, format='json')
        self.assertEqual(response.status_code, 200)
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertEqual(self.api.patch(self.detail(n), {'message': 'hacked'}, format='json').status_code, 400)
        n.refresh_from_db()
        self.assertEqual(n.message, 'Hello')

    def test_actions(self):
        n = self.make()
        self.make()
        self.assertEqual(self.api.post(self.detail(n, 'mark-read')).status_code, 200)
        self.assertEqual(self.api.get(reverse('api:notification-unread-count')).data['unread_count'], 1)
        self.assertEqual(self.api.post(reverse('api:notification-mark-all-read')).data['marked_count'], 1)
        self.assertEqual(self.api.get(reverse('api:notification-preferences')).status_code, 200)
        response = self.api.patch(reverse('api:notification-preferences'), {'digest_frequency': 'weekly'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(NotificationPreference.objects.get(user=self.user).digest_frequency, 'weekly')
