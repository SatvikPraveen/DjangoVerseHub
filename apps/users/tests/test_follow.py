# File: DjangoVerseHub/apps/users/tests/test_follow.py

from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError, transaction
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.articles.models import Article
from apps.comments.models import Comment
from ..models import Follow

User = get_user_model()


def make_user(username, **extra):
    return User.objects.create_user(
        email=f'{username}@example.com', username=username, password='pass12345', **extra
    )


class FollowModelTest(TestCase):
    """Follow model and CustomUser helper behaviour"""

    def setUp(self):
        self.alice = make_user('alice')
        self.bob = make_user('bob')

    def test_follow_and_unfollow_helpers(self):
        follow, created = self.alice.follow(self.bob)
        self.assertTrue(created)
        self.assertIsInstance(follow, Follow)
        self.assertTrue(self.alice.is_following(self.bob))
        self.assertFalse(self.bob.is_following(self.alice))
        self.assertEqual(self.bob.followers_count, 1)
        self.assertEqual(self.alice.following_count, 1)
        self.assertIn(self.bob, self.alice.following)
        self.assertIn(self.alice, self.bob.followers)

        # Idempotent
        _, created_again = self.alice.follow(self.bob)
        self.assertFalse(created_again)
        self.assertEqual(Follow.objects.count(), 1)

        self.assertTrue(self.alice.unfollow(self.bob))
        self.assertFalse(self.alice.unfollow(self.bob))
        self.assertFalse(self.alice.is_following(self.bob))

    def test_self_follow_is_noop(self):
        follow, created = self.alice.follow(self.alice)
        self.assertIsNone(follow)
        self.assertFalse(created)
        self.assertEqual(Follow.objects.count(), 0)

    def test_unique_and_no_self_follow_constraints(self):
        Follow.objects.create(follower=self.alice, following=self.bob)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.alice, following=self.bob)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Follow.objects.create(follower=self.alice, following=self.alice)


class FollowViewsTest(TestCase):
    """Web follow/unfollow endpoints and the profile follow button"""

    def setUp(self):
        self.client = Client()
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.follow_url = reverse('users:follow', kwargs={'pk': self.bob.pk})
        self.unfollow_url = reverse('users:unfollow', kwargs={'pk': self.bob.pk})
        self.profile_url = reverse('users:profile', kwargs={'pk': self.bob.pk})

    def test_follow_requires_login(self):
        response = self.client.post(self.follow_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:login'), response.url)
        self.assertFalse(Follow.objects.exists())

    def test_follow_requires_login_json(self):
        response = self.client.post(self.follow_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()['success'])

    def test_follow_rejects_get(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.follow_url).status_code, 405)

    def test_follow_redirects_back(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.follow_url, HTTP_REFERER=self.profile_url)
        self.assertRedirects(response, self.profile_url)
        self.assertTrue(self.alice.is_following(self.bob))

    def test_follow_ignores_external_referer(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.follow_url, HTTP_REFERER='https://evil.example/phish')
        self.assertRedirects(response, self.profile_url)

    def test_follow_and_unfollow_json(self):
        self.client.force_login(self.alice)
        response = self.client.post(self.follow_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['is_following'])
        self.assertEqual(data['followers_count'], 1)

        response = self.client.post(self.unfollow_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        data = response.json()
        self.assertTrue(data['success'])
        self.assertFalse(data['is_following'])
        self.assertEqual(data['followers_count'], 0)
        self.assertFalse(self.alice.is_following(self.bob))

    def test_cannot_follow_self(self):
        self.client.force_login(self.alice)
        url = reverse('users:follow', kwargs={'pk': self.alice.pk})
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Follow.objects.exists())

    def test_cannot_follow_private_profile(self):
        self.bob.profile.is_public = False
        self.bob.profile.save()
        self.client.force_login(self.alice)
        response = self.client.post(self.follow_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Follow.objects.exists())

    def test_follow_unknown_user_404(self):
        self.client.force_login(self.alice)
        url = reverse('users:follow', kwargs={'pk': '00000000-0000-0000-0000-000000000000'})
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_profile_shows_follow_button_state(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.profile_url)
        self.assertContains(response, self.follow_url)
        self.assertContains(response, 'Follow')

        self.alice.follow(self.bob)
        response = self.client.get(self.profile_url)
        self.assertContains(response, self.unfollow_url)
        self.assertContains(response, 'Following')

    def test_own_profile_has_no_follow_button(self):
        self.client.force_login(self.bob)
        response = self.client.get(self.profile_url)
        self.assertNotContains(response, self.follow_url)
        self.assertContains(response, reverse('users:profile_edit'))

    def test_anonymous_profile_view_links_to_login(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('users:login'))


class FollowingPageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.carol = make_user('carol')
        self.alice.follow(self.bob)
        self.carol.follow(self.alice)

    def test_requires_login(self):
        response = self.client.get(reverse('users:following'))
        self.assertEqual(response.status_code, 302)

    def test_lists_following_and_followers(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse('users:following'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['following']), [self.bob])
        self.assertEqual(list(response.context['followers']), [self.carol])
        self.assertContains(response, 'bob')
        self.assertContains(response, 'carol')
        # Bob is followed -> unfollow button; Carol is not -> follow button
        self.assertContains(response, reverse('users:unfollow', kwargs={'pk': self.bob.pk}))
        self.assertContains(response, reverse('users:follow', kwargs={'pk': self.carol.pk}))


class LeaderboardTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.dave = make_user('dave')
        self.hidden = make_user('hidden')
        self.hidden.profile.is_public = False
        self.hidden.profile.save()

        def article(author, title, status='published', views=0):
            return Article.objects.create(
                author=author, title=title, content='x' * 50, status=status, views_count=views
            )

        article(self.alice, 'A1', views=10)
        article(self.alice, 'A2', views=5)
        article(self.alice, 'A3 draft', status='draft', views=999)
        article(self.bob, 'B1', views=100)
        article(self.hidden, 'H1', views=1000)

    def test_leaderboard_is_public_and_ranked(self):
        response = self.client.get(reverse('users:leaderboard'))
        self.assertEqual(response.status_code, 200)
        leaders = list(response.context['leaders'])
        self.assertEqual([u.username for u in leaders], ['alice', 'bob'])
        self.assertEqual(leaders[0].published_count, 2)
        self.assertEqual(leaders[0].total_views, 15)  # draft views excluded
        self.assertEqual(leaders[1].published_count, 1)
        self.assertEqual(leaders[1].total_views, 100)
        # Users without published articles and private profiles are excluded
        self.assertNotIn(self.dave, leaders)
        self.assertNotIn(self.hidden, leaders)


class ActivityPageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.alice = make_user('alice')
        self.article = Article.objects.create(
            author=self.alice, title='Hello World', content='x' * 50, status='published'
        )
        Comment.objects.create(
            content_type=ContentType.objects.get_for_model(Article),
            object_id=str(self.article.pk),
            author=self.alice,
            content='Nice article',
        )

    def test_requires_login(self):
        self.assertEqual(self.client.get(reverse('users:activity')).status_code, 302)

    def test_shows_recent_articles_and_comments(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse('users:activity'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hello World')
        self.assertContains(response, 'Nice article')
        types = [a['type'] for a in response.context['recent_activities']]
        self.assertIn('article_published', types)
        self.assertIn('comment_posted', types)

    def test_profile_stats_reflect_activity(self):
        response = self.client.get(reverse('users:profile', kwargs={'pk': self.alice.pk}))
        self.assertEqual(response.context['articles_count'], 1)
        self.assertEqual(response.context['comments_count'], 1)
        self.assertContains(response, 'Hello World')


class FollowAPITest(TestCase):
    """DRF follow/unfollow/followers/following actions"""

    def setUp(self):
        self.client = APIClient()
        self.alice = make_user('alice')
        self.bob = make_user('bob')
        self.carol = make_user('carol')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=self.alice).key)

    def test_follow_and_unfollow(self):
        url = reverse('users:user-follow', kwargs={'pk': self.bob.pk})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_following'])
        self.assertEqual(response.data['followers_count'], 1)

        # Second follow is a no-op
        self.assertEqual(self.client.post(url).status_code, status.HTTP_200_OK)
        self.assertEqual(Follow.objects.count(), 1)

        url = reverse('users:user-unfollow', kwargs={'pk': self.bob.pk})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_following'])
        self.assertEqual(Follow.objects.count(), 0)

    def test_cannot_follow_self(self):
        url = reverse('users:user-follow', kwargs={'pk': self.alice.pk})
        self.assertEqual(self.client.post(url).status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_follow_private_profile(self):
        self.bob.profile.is_public = False
        self.bob.profile.save()
        url = reverse('users:user-follow', kwargs={'pk': self.bob.pk})
        self.assertEqual(self.client.post(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_follow_requires_auth(self):
        self.client.credentials()
        url = reverse('users:user-follow', kwargs={'pk': self.bob.pk})
        self.assertEqual(self.client.post(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_followers_and_following_lists(self):
        self.alice.follow(self.bob)
        self.carol.follow(self.bob)

        response = self.client.get(reverse('users:user-followers', kwargs={'pk': self.bob.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual({u['username'] for u in response.data['results']}, {'alice', 'carol'})

        response = self.client.get(reverse('users:user-following', kwargs={'pk': self.alice.pk}))
        self.assertEqual([u['username'] for u in response.data['results']], ['bob'])

    def test_user_detail_includes_follow_counts(self):
        self.alice.follow(self.bob)
        response = self.client.get(reverse('users:user-detail', kwargs={'pk': self.bob.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['followers_count'], 1)
        self.assertTrue(response.data['is_following'])


class UserAPIPrivacyTest(TestCase):
    """Private data is only exposed to the owner"""

    def setUp(self):
        self.client = APIClient()
        self.alice = make_user('alice', phone_number='+1234567890')
        self.bob = make_user('bob', phone_number='+1987654321')
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=self.alice).key)

    def test_other_users_private_fields_hidden(self):
        response = self.client.get(reverse('users:user-detail', kwargs={'pk': self.bob.pk}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in ('email', 'phone_number', 'date_of_birth', 'login_count', 'last_login'):
            self.assertNotIn(field, response.data)
        self.assertNotIn('email_notifications', response.data['profile'])
        self.assertNotIn('email', response.data['profile'])

    def test_show_email_setting_respected(self):
        self.bob.profile.show_email = True
        self.bob.profile.save()
        response = self.client.get(reverse('users:user-detail', kwargs={'pk': self.bob.pk}))
        self.assertEqual(response.data['email'], self.bob.email)

    def test_own_private_fields_visible(self):
        response = self.client.get(reverse('users:user-me'))
        self.assertEqual(response.data['phone_number'], '+1234567890')
        self.assertIn('email_notifications', response.data['profile'])

    def test_cannot_update_other_user(self):
        url = reverse('users:user-detail', kwargs={'pk': self.bob.pk})
        response = self.client.patch(url, {'first_name': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.first_name, '')

    def test_cannot_change_email_or_username_via_update(self):
        url = reverse('users:user-detail', kwargs={'pk': self.alice.pk})
        response = self.client.patch(url, {'email': 'new@example.com', 'username': 'root', 'first_name': 'A'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.email, 'alice@example.com')
        self.assertEqual(self.alice.username, 'alice')
        self.assertEqual(self.alice.first_name, 'A')

    def test_me_patch(self):
        response = self.client.patch(reverse('users:user-me'), {'last_name': 'Liddell'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['last_name'], 'Liddell')

    def test_no_account_delete_endpoint(self):
        url = reverse('users:user-detail', kwargs={'pk': self.alice.pk})
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_login_with_username(self):
        self.client.credentials()
        response = self.client.post(reverse('users:user-login'), {'username': 'bob', 'password': 'pass12345'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'bob')


class LoginFormUsernameTest(TestCase):
    def test_web_login_with_username(self):
        make_user('alice')
        response = Client().post(reverse('users:login'), {'username': 'alice', 'password': 'pass12345'})
        self.assertEqual(response.status_code, 302)

    def test_login_next_open_redirect_blocked(self):
        make_user('alice')
        response = Client().post(
            reverse('users:login') + '?next=https://evil.example/',
            {'username': 'alice', 'password': 'pass12345'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.example', response.url)
