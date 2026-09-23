# File: DjangoVerseHub/apps/articles/tests/test_engagement.py
"""Tests for bookmarks, likes, revisions, view tracking and the access-control fixes."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.articles.models import Article, ArticleLike, ArticleRevision, Bookmark, Category, Tag
from apps.notifications.models import Notification

User = get_user_model()

LONG_CONTENT = 'Some sufficiently long article content for validation to pass. ' * 5


def make_user(email, **extra):
    return User.objects.create_user(email=email, username=email.split('@')[0], first_name='Test', last_name='User', **extra)


class EngagementBase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.author = make_user('author@example.com')
        self.reader = make_user('reader@example.com')
        self.staff = make_user('staff@example.com', is_staff=True)
        self.article = Article.objects.create(
            title='Engagement Article', content=LONG_CONTENT, author=self.author, status='published'
        )
        self.draft = Article.objects.create(
            title='Secret Draft', content=LONG_CONTENT, author=self.author, status='draft'
        )


# ──────────────────────────────────────────────────────────────────────────────
# Bookmarks
# ──────────────────────────────────────────────────────────────────────────────

class BookmarkModelTest(EngagementBase):
    def test_toggle_creates_then_removes(self):
        self.assertTrue(Bookmark.toggle(self.reader, self.article))
        self.assertEqual(Bookmark.objects.count(), 1)
        self.assertTrue(self.article.is_bookmarked_by(self.reader))

        self.assertFalse(Bookmark.toggle(self.reader, self.article))
        self.assertEqual(Bookmark.objects.count(), 0)
        self.assertFalse(self.article.is_bookmarked_by(self.reader))

    def test_unique_per_user_and_article(self):
        Bookmark.objects.create(user=self.reader, article=self.article)
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Bookmark.objects.create(user=self.reader, article=self.article)

    def test_related_names(self):
        Bookmark.objects.create(user=self.reader, article=self.article)
        self.assertEqual(self.reader.bookmarks.count(), 1)
        self.assertEqual(self.article.bookmarks.count(), 1)


class BookmarkViewTest(EngagementBase):
    def url(self, article=None):
        return reverse('articles:bookmark', kwargs={'slug': (article or self.article).slug})

    def test_requires_login(self):
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Bookmark.objects.count(), 0)

    def test_get_not_allowed(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_toggle_redirects_for_regular_post(self):
        self.client.force_login(self.reader)
        response = self.client.post(self.url())
        self.assertRedirects(response, self.article.get_absolute_url())
        self.assertTrue(Bookmark.objects.filter(user=self.reader, article=self.article).exists())

        self.client.post(self.url())
        self.assertFalse(Bookmark.objects.filter(user=self.reader, article=self.article).exists())

    def test_toggle_returns_json_for_xhr(self):
        self.client.force_login(self.reader)
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'bookmarked': True})
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'bookmarked': False})

    def test_cannot_bookmark_draft(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(self.url(self.draft)).status_code, 404)

    def test_bookmarks_page_lists_bookmarked_articles(self):
        other = Article.objects.create(title='Not Bookmarked', content=LONG_CONTENT, author=self.author, status='published')
        Bookmark.objects.create(user=self.reader, article=self.article)
        self.client.force_login(self.reader)
        response = self.client.get(reverse('articles:bookmarks'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Engagement Article')
        self.assertNotContains(response, other.title)
        self.assertContains(response, '<h1>Bookmarks</h1>', html=True)

    def test_detail_page_shows_bookmark_state(self):
        self.client.force_login(self.reader)
        response = self.client.get(self.article.get_absolute_url())
        self.assertContains(response, 'id="bookmark-button"')
        self.assertFalse(response.context['is_bookmarked'])
        Bookmark.objects.create(user=self.reader, article=self.article)
        response = self.client.get(self.article.get_absolute_url())
        self.assertTrue(response.context['is_bookmarked'])


# ──────────────────────────────────────────────────────────────────────────────
# Likes
# ──────────────────────────────────────────────────────────────────────────────

class ArticleLikeModelTest(EngagementBase):
    def test_toggle_keeps_likes_count_in_sync(self):
        liked, count = ArticleLike.toggle(self.reader, self.article)
        self.assertTrue(liked)
        self.assertEqual(count, 1)
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 1)
        self.assertTrue(self.article.is_liked_by(self.reader))

        liked, count = ArticleLike.toggle(self.reader, self.article)
        self.assertFalse(liked)
        self.assertEqual(count, 0)
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 0)

    def test_multiple_users(self):
        ArticleLike.toggle(self.reader, self.article)
        ArticleLike.toggle(self.staff, self.article)
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 2)
        self.assertEqual(self.article.likes.count(), 2)

    def test_like_notifies_author(self):
        ArticleLike.toggle(self.reader, self.article)
        notification = Notification.objects.get(recipient=self.author)
        self.assertEqual(notification.notification_type, 'like')
        self.assertEqual(notification.sender, self.reader)

    def test_self_like_does_not_notify(self):
        ArticleLike.toggle(self.author, self.article)
        self.assertFalse(Notification.objects.filter(recipient=self.author).exists())


class ArticleLikeViewTest(EngagementBase):
    def url(self, article=None):
        return reverse('articles:like', kwargs={'slug': (article or self.article).slug})

    def test_requires_login(self):
        self.assertEqual(self.client.post(self.url()).status_code, 302)
        self.assertEqual(ArticleLike.objects.count(), 0)

    def test_toggle_json(self):
        self.client.force_login(self.reader)
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'liked': True, 'likes_count': 1})
        response = self.client.post(self.url(), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.json(), {'liked': False, 'likes_count': 0})

    def test_toggle_redirect(self):
        self.client.force_login(self.reader)
        response = self.client.post(self.url())
        self.assertRedirects(response, self.article.get_absolute_url())
        self.article.refresh_from_db()
        self.assertEqual(self.article.likes_count, 1)

    def test_cannot_like_draft(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.post(self.url(self.draft)).status_code, 404)


# ──────────────────────────────────────────────────────────────────────────────
# Revisions
# ──────────────────────────────────────────────────────────────────────────────

class ArticleRevisionTest(EngagementBase):
    def test_no_revision_on_create(self):
        self.assertEqual(ArticleRevision.objects.count(), 0)

    def test_revision_created_when_content_changes(self):
        self.article.title = 'Changed Title'
        self.article.save(editor=self.author)

        revision = ArticleRevision.objects.get()
        self.assertEqual(revision.article, self.article)
        self.assertEqual(revision.editor, self.author)
        self.assertEqual(revision.title, 'Engagement Article')
        self.assertEqual(revision.content, LONG_CONTENT)

    def test_no_revision_when_tracked_fields_unchanged(self):
        self.article.is_featured = True
        self.article.save()
        self.article.increment_views()
        self.assertEqual(ArticleRevision.objects.count(), 0)

    def test_no_revision_for_update_fields_without_tracked_fields(self):
        self.article.title = 'Changed in memory only'
        self.article.save(update_fields=['is_featured'])
        self.assertEqual(ArticleRevision.objects.count(), 0)

    def test_restore(self):
        self.article.title = 'Second Title'
        self.article.summary = 'Second summary'
        self.article.save(editor=self.author)
        revision = ArticleRevision.objects.get()

        revision.restore(editor=self.staff)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, 'Engagement Article')
        self.assertEqual(self.article.summary, '')
        # Restoring snapshots the superseded text, so history keeps growing
        self.assertEqual(ArticleRevision.objects.count(), 2)
        newest = ArticleRevision.objects.order_by('-created_at', '-id').first()
        self.assertEqual(newest.title, 'Second Title')
        self.assertEqual(newest.editor, self.staff)

    def test_form_edit_records_editor(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse('articles:edit', kwargs={'slug': self.article.slug}),
            {'title': 'Edited Via Form', 'content': LONG_CONTENT, 'status': 'published', 'allow_comments': True},
        )
        self.assertEqual(response.status_code, 302)
        revision = ArticleRevision.objects.get()
        self.assertEqual(revision.editor, self.author)
        self.assertEqual(revision.title, 'Engagement Article')


class ArticleRevisionViewTest(EngagementBase):
    def setUp(self):
        super().setUp()
        self.article.title = 'Renamed Article'
        self.article.save(editor=self.author)
        self.revision = ArticleRevision.objects.get()
        self.list_url = reverse('articles:revisions', kwargs={'slug': self.article.slug})
        self.restore_url = reverse(
            'articles:revision_restore', kwargs={'slug': self.article.slug, 'pk': self.revision.pk}
        )

    def test_anonymous_redirected(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 302)

    def test_other_user_gets_404(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.list_url).status_code, 404)
        self.assertEqual(self.client.post(self.restore_url).status_code, 404)

    def test_author_sees_history(self):
        self.client.force_login(self.author)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Engagement Article')
        self.assertIn(self.revision, response.context['revisions'])

    def test_staff_can_view_and_restore(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)
        response = self.client.post(self.restore_url)
        self.assertRedirects(response, self.list_url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.title, 'Engagement Article')

    def test_restore_requires_post(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(self.restore_url).status_code, 405)

    def test_restore_rejects_revision_of_other_article(self):
        other = Article.objects.create(title='Other Article', content=LONG_CONTENT, author=self.author)
        other.title = 'Other Renamed'
        other.save()
        other_revision = other.revisions.get()
        self.client.force_login(self.author)
        url = reverse('articles:revision_restore', kwargs={'slug': self.article.slug, 'pk': other_revision.pk})
        self.assertEqual(self.client.post(url).status_code, 404)


# ──────────────────────────────────────────────────────────────────────────────
# View tracking, related articles, reading time, slugs
# ──────────────────────────────────────────────────────────────────────────────

class ViewTrackingTest(EngagementBase):
    def test_increment_without_request_always_counts(self):
        self.article.increment_views()
        self.article.increment_views()
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 2)

    def test_increment_uses_database_value(self):
        stale = Article.objects.get(pk=self.article.pk)
        self.article.increment_views()
        stale.increment_views()
        self.assertEqual(stale.views_count, 2)

    def test_repeat_visits_deduplicated(self):
        url = self.article.get_absolute_url()
        self.client.get(url)
        self.client.get(url)
        self.client.get(url)
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 1)

    def test_distinct_visitors_counted(self):
        url = self.article.get_absolute_url()
        self.client.get(url, REMOTE_ADDR='10.0.0.1')
        self.client.get(url, REMOTE_ADDR='10.0.0.2')
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, 2)

    def test_draft_views_not_counted(self):
        self.client.force_login(self.author)
        self.client.get(self.draft.get_absolute_url())
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.views_count, 0)


class RelatedArticlesTest(EngagementBase):
    def setUp(self):
        super().setUp()
        self.category = Category.objects.create(name='Django')
        self.tag_a = Tag.objects.create(name='python')
        self.tag_b = Tag.objects.create(name='web')
        self.article.category = self.category
        self.article.save()
        self.article.tags.set([self.tag_a, self.tag_b])

    def _article(self, title, tags=(), category=None, status='published'):
        article = Article.objects.create(title=title, content=LONG_CONTENT, author=self.author, status=status, category=category)
        article.tags.set(tags)
        return article

    def test_orders_by_shared_tags_then_category(self):
        two_tags = self._article('Two Tags', tags=[self.tag_a, self.tag_b])
        one_tag = self._article('One Tag', tags=[self.tag_b])
        same_category = self._article('Same Category', category=self.category)
        self._article('Unrelated')
        self._article('Draft Related', tags=[self.tag_a, self.tag_b], status='draft')

        related = self.article.get_related_articles(limit=5)
        self.assertEqual([a.title for a in related], [two_tags.title, one_tag.title, same_category.title])
        self.assertNotIn(self.article, related)

    def test_limit_respected(self):
        for i in range(4):
            self._article(f'Tagged {i}', tags=[self.tag_a])
        self.assertEqual(len(self.article.get_related_articles(limit=2)), 2)

    def test_query_count_is_bounded(self):
        for i in range(6):
            self._article(f'Tagged {i}', tags=[self.tag_a], category=self.category)
        with self.assertNumQueries(3):  # tag ids, tag matches, (category top-up)
            related = self.article.get_related_articles(limit=10)
            [a.author.email for a in related]  # select_related, no extra queries
        self.assertEqual(len(related), 6)


class ReadingTimeAndSlugTest(EngagementBase):
    def test_reading_time_rounds_up(self):
        self.article.content = 'word ' * 201
        self.assertEqual(self.article.reading_time, 2)
        self.article.content = '<p>' + 'word ' * 50 + '</p>'
        self.assertEqual(self.article.reading_time, 1)

    def test_slug_collision_gets_suffix(self):
        a = Article.objects.create(title='Same Title', content=LONG_CONTENT, author=self.author)
        b = Article.objects.create(title='Same Title', content=LONG_CONTENT, author=self.author)
        c = Article.objects.create(title='Same Title', content=LONG_CONTENT, author=self.author)
        self.assertEqual({a.slug, b.slug, c.slug}, {'same-title', 'same-title-1', 'same-title-2'})

    def test_slug_stable_on_resave(self):
        slug = self.article.slug
        self.article.title = 'A Brand New Title'
        self.article.save()
        self.assertEqual(self.article.slug, slug)

    def test_category_and_tag_slug_collisions(self):
        Category.objects.create(name='C++', slug='c')
        second = Category.objects.create(name='C')
        self.assertEqual(second.slug, 'c-1')
        Tag.objects.create(name='Go!', slug='go')
        self.assertEqual(Tag.objects.create(name='Go').slug, 'go-1')

    def test_article_count_reads_annotation(self):
        tag = Tag.objects.create(name='counted')
        self.article.tags.add(tag)
        self.draft.tags.add(tag)
        annotated = Tag.objects.with_article_count().get(pk=tag.pk)
        with self.assertNumQueries(0):
            self.assertEqual(annotated.article_count, 1)
        self.assertEqual(Tag.objects.get(pk=tag.pk).article_count, 1)


# ──────────────────────────────────────────────────────────────────────────────
# Access control
# ──────────────────────────────────────────────────────────────────────────────

class DraftVisibilityTest(EngagementBase):
    def test_anonymous_cannot_see_draft(self):
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)

    def test_other_user_cannot_see_draft(self):
        self.client.force_login(self.reader)
        self.assertEqual(self.client.get(self.draft.get_absolute_url()).status_code, 404)

    def test_author_and_staff_can_see_draft(self):
        for user in (self.author, self.staff):
            self.client.force_login(user)
            response = self.client.get(self.draft.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'only visible to you')

    def test_draft_absent_from_public_list(self):
        response = self.client.get(reverse('articles:list'))
        self.assertNotContains(response, 'Secret Draft')

    def test_staff_can_edit_and_delete_others_articles(self):
        self.client.force_login(self.staff)
        edit_url = reverse('articles:edit', kwargs={'slug': self.article.slug})
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        delete_url = reverse('articles:delete', kwargs={'slug': self.article.slug})
        self.assertEqual(self.client.get(delete_url).status_code, 200)

    def test_non_owner_cannot_delete(self):
        self.client.force_login(self.reader)
        delete_url = reverse('articles:delete', kwargs={'slug': self.article.slug})
        self.assertEqual(self.client.post(delete_url).status_code, 404)
        self.assertTrue(Article.objects.filter(pk=self.article.pk).exists())

    def test_non_staff_cannot_feature_via_form(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse('articles:edit', kwargs={'slug': self.article.slug}),
            {'title': self.article.title, 'content': LONG_CONTENT, 'status': 'published', 'is_featured': 'on'},
        )
        self.article.refresh_from_db()
        self.assertFalse(self.article.is_featured)

    def test_drafts_page(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('articles:drafts'))
        self.assertContains(response, 'Secret Draft')
        self.assertNotContains(response, 'Engagement Article')
        self.assertContains(response, '<h1>My Drafts</h1>', html=True)


# ──────────────────────────────────────────────────────────────────────────────
# API
# ──────────────────────────────────────────────────────────────────────────────

class EngagementAPITest(EngagementBase):
    def setUp(self):
        super().setUp()
        self.api = APIClient()
        self.reader_token = Token.objects.create(user=self.reader)
        self.author_token = Token.objects.create(user=self.author)

    def auth(self, token):
        self.api.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

    def test_like_action_toggles(self):
        self.auth(self.reader_token)
        url = reverse('articles:article-like', kwargs={'pk': self.article.pk})
        response = self.api.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'liked': True, 'likes_count': 1})
        response = self.api.post(url)
        self.assertEqual(response.data, {'liked': False, 'likes_count': 0})

    def test_like_requires_auth(self):
        url = reverse('articles:article-like', kwargs={'pk': self.article.pk})
        self.assertEqual(self.api.post(url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_bookmark_action_toggles(self):
        self.auth(self.reader_token)
        url = reverse('articles:article-bookmark', kwargs={'pk': self.article.pk})
        self.assertEqual(self.api.post(url).data, {'bookmarked': True})
        self.assertEqual(self.api.post(url).data, {'bookmarked': False})

    def test_serializer_flags_reflect_current_user(self):
        Bookmark.objects.create(user=self.reader, article=self.article)
        ArticleLike.toggle(self.reader, self.article)

        detail_url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        anonymous = self.api.get(detail_url).data
        self.assertFalse(anonymous['liked'])
        self.assertFalse(anonymous['bookmarked'])

        self.auth(self.reader_token)
        mine = self.api.get(detail_url).data
        self.assertTrue(mine['liked'])
        self.assertTrue(mine['bookmarked'])
        self.assertEqual(mine['likes_count'], 1)

        listed = self.api.get(reverse('articles:article-list')).data['results']
        self.assertTrue(listed[0]['liked'])
        self.assertTrue(listed[0]['bookmarked'])

    def test_bookmarked_list_action(self):
        Bookmark.objects.create(user=self.reader, article=self.article)
        self.auth(self.reader_token)
        response = self.api.get(reverse('articles:article-bookmarked'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([a['title'] for a in response.data['results']], ['Engagement Article'])

    def test_draft_hidden_from_other_users(self):
        url = reverse('articles:article-detail', kwargs={'pk': self.draft.pk})
        self.assertEqual(self.api.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.auth(self.reader_token)
        self.assertEqual(self.api.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.auth(self.author_token)
        self.assertEqual(self.api.get(url).status_code, status.HTTP_200_OK)

    def test_non_staff_cannot_set_is_featured(self):
        self.auth(self.author_token)
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        response = self.api.patch(url, {'is_featured': True})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.article.refresh_from_db()
        self.assertFalse(self.article.is_featured)

    def test_update_creates_revision_with_editor(self):
        self.auth(self.author_token)
        url = reverse('articles:article-detail', kwargs={'pk': self.article.pk})
        self.api.patch(url, {'title': 'API Renamed Title'})
        revision = ArticleRevision.objects.get()
        self.assertEqual(revision.editor, self.author)
        self.assertEqual(revision.title, 'Engagement Article')

    def test_revisions_action_author_only(self):
        self.article.title = 'Renamed'
        self.article.save()
        url = reverse('articles:article-revisions', kwargs={'pk': self.article.pk})
        self.auth(self.reader_token)
        self.assertEqual(self.api.get(url).status_code, status.HTTP_403_FORBIDDEN)
        self.auth(self.author_token)
        response = self.api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['title'], 'Engagement Article')

    def test_list_query_count_is_constant(self):
        tag = Tag.objects.create(name='shared')
        for i in range(8):
            article = Article.objects.create(title=f'Bulk {i}', content=LONG_CONTENT, author=self.author, status='published')
            article.tags.add(tag)
        self.auth(self.reader_token)
        url = reverse('articles:article-list')
        with self.assertNumQueries(5):
            # token auth, count, articles (+user flags), tags prefetch (+counts), comment counts
            response = self.api.get(url, {'page_size': 50})
        self.assertEqual(len(response.data['results']), 9)


# ──────────────────────────────────────────────────────────────────────────────
# Remaining page templates
# ──────────────────────────────────────────────────────────────────────────────

class ListingPagesTest(EngagementBase):
    def setUp(self):
        super().setUp()
        self.tag = Tag.objects.create(name='Testing')
        self.article.tags.add(self.tag)
        self.draft.tags.add(self.tag)

    def test_tag_list_page(self):
        response = self.client.get(reverse('articles:tags'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Testing')
        tag = [t for t in response.context['tags'] if t.pk == self.tag.pk][0]
        self.assertEqual(tag.article_count, 1)  # drafts are not counted

    def test_tag_detail_page(self):
        response = self.client.get(reverse('articles:tag_detail', kwargs={'slug': self.tag.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Engagement Article')
        self.assertNotContains(response, 'Secret Draft')

    def test_tag_detail_404(self):
        self.assertEqual(self.client.get(reverse('articles:tag_detail', kwargs={'slug': 'nope'})).status_code, 404)

    def test_my_articles_page(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('articles:my_articles'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>My Articles</h1>', html=True)
        self.assertContains(response, 'Engagement Article')
        self.assertContains(response, 'Secret Draft')

    def test_my_articles_requires_login(self):
        self.assertEqual(self.client.get(reverse('articles:my_articles')).status_code, 302)

    def test_list_page_title_defaults_to_articles(self):
        response = self.client.get(reverse('articles:list'))
        self.assertContains(response, '<h1>Articles</h1>', html=True)

    def test_list_pagination_preserves_query_string(self):
        for i in range(13):
            Article.objects.create(title=f'Paged {i}', content=LONG_CONTENT, author=self.author, status='published')
        response = self.client.get(reverse('articles:list'), {'ordering': 'title'})
        self.assertContains(response, 'ordering=title&amp;page=2')

    def test_detail_page_renders_tags_category_and_related(self):
        category = Category.objects.create(name='Guides')
        self.article.category = category
        self.article.save()
        related = Article.objects.create(title='Related Piece', content=LONG_CONTENT, author=self.author, status='published')
        related.tags.add(self.tag)
        self.client.force_login(self.reader)
        ArticleLike.toggle(self.reader, self.article)
        response = self.client.get(self.article.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('articles:tag_detail', kwargs={'slug': self.tag.slug}))
        self.assertContains(response, reverse('articles:category_detail', kwargs={'slug': category.slug}))
        self.assertContains(response, 'Related Piece')
        self.assertContains(response, 'bi-heart-fill')
        self.assertContains(response, f"object_id={self.article.id}")
        self.assertNotContains(response, 'History</a>')  # reader is not the author
