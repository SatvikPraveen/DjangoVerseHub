# File: DjangoVerseHub/apps/notifications/tests/test_signals.py
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.articles.models import Article, Category
from apps.comments.models import Comment
from apps.notifications.models import Notification, NotificationPreference
from apps.users.models import Follow

User = get_user_model()


def _optional_model(app_label, model_name):
    try:
        return django_apps.get_model(app_label, model_name)
    except LookupError:
        return None


class SignalTestBase(TestCase):
    """Common fixtures; silences the comments app's own email/moderation tasks."""

    def setUp(self):
        # The comments app enqueues email + moderation tasks on every comment.
        # They are not under test here and must not break these tests.
        for target in ("apps.comments.signals.send_comment_notification", "apps.comments.signals.moderate_comment"):
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.author = User.objects.create_user(email="author@test.com", password="testpass123", username="author")
        self.commenter = User.objects.create_user(
            email="commenter@test.com",
            password="testpass123",
            username="commenter",
            first_name="Casey",
            last_name="Commenter",
        )
        self.category = Category.objects.create(name="General", slug="general")
        self.article = Article.objects.create(
            title="Signal Test Article",
            slug="signal-test-article",
            author=self.author,
            category=self.category,
            content="Article content",
            status="published",
        )
        self.article_ct = ContentType.objects.get_for_model(Article)

    def make_comment(self, author, content="Nice!", parent=None):
        return Comment.objects.create(
            author=author,
            content_type=self.article_ct,
            object_id=str(self.article.pk),
            content=content,
            parent=parent,
        )


class CommentNotificationSignalTest(SignalTestBase):
    @patch("apps.notifications.signals.send_notification_to_user")
    def test_comment_on_article_notifies_author(self, mock_send):
        initial = Notification.objects.count()
        self.make_comment(self.commenter, "Great article!")

        self.assertEqual(Notification.objects.count(), initial + 1)
        notification = Notification.objects.latest("created_at")
        self.assertEqual(notification.recipient, self.author)
        self.assertEqual(notification.sender, self.commenter)
        self.assertEqual(notification.notification_type, "comment")
        self.assertIn("Casey Commenter commented on your article", notification.message)
        self.assertEqual(notification.content_object, self.article)
        self.assertEqual(notification.url, self.article.get_absolute_url())
        mock_send.assert_called_once_with(notification)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_author_commenting_own_article_no_notification(self, mock_send):
        initial = Notification.objects.count()
        self.make_comment(self.author, "My own comment")
        self.assertEqual(Notification.objects.count(), initial)
        mock_send.assert_not_called()

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_reply_notifies_parent_comment_author(self, mock_send):
        parent = self.make_comment(self.author, "Parent comment")
        Notification.objects.all().delete()
        mock_send.reset_mock()

        self.make_comment(self.commenter, "Reply", parent=parent)

        # Parent author == article author here: exactly one "replied" notification.
        notifications = Notification.objects.filter(recipient=self.author, sender=self.commenter)
        self.assertEqual(notifications.count(), 1)
        self.assertIn("replied to your comment", notifications.get().message)
        self.assertEqual(notifications.get().content_object, parent)
        self.assertEqual(mock_send.call_count, 1)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_reply_notifies_both_parent_author_and_article_author(self, mock_send):
        third = User.objects.create_user(email="third@test.com", password="x", username="third")
        parent = self.make_comment(third, "Parent by third")
        Notification.objects.all().delete()
        mock_send.reset_mock()

        self.make_comment(self.commenter, "Reply", parent=parent)

        self.assertTrue(Notification.objects.filter(recipient=self.author, message__contains="commented").exists())
        self.assertTrue(Notification.objects.filter(recipient=third, message__contains="replied").exists())
        self.assertEqual(mock_send.call_count, 2)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_reply_to_own_comment_does_not_notify_self(self, mock_send):
        parent = self.make_comment(self.commenter, "Parent")
        Notification.objects.all().delete()
        mock_send.reset_mock()

        self.make_comment(self.commenter, "Reply to myself", parent=parent)

        # Article author still gets a comment notification; the replier does not notify themselves.
        self.assertFalse(Notification.objects.filter(recipient=self.commenter).exists())
        self.assertEqual(Notification.objects.filter(recipient=self.author).count(), 1)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_signal_does_not_fire_on_update(self, mock_send):
        comment = self.make_comment(self.commenter, "Original body")
        count_after_create = Notification.objects.count()
        mock_send.reset_mock()

        comment.content = "Edited body"
        comment.save()

        self.assertEqual(Notification.objects.count(), count_after_create)
        mock_send.assert_not_called()

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_duplicate_unread_notification_is_not_created(self, mock_send):
        self.make_comment(self.commenter, "First")
        self.make_comment(self.commenter, "Second")
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.author, sender=self.commenter, notification_type="comment"
            ).count(),
            1,
        )
        self.assertEqual(mock_send.call_count, 1)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_new_notification_after_previous_was_read(self, mock_send):
        self.make_comment(self.commenter, "First")
        Notification.objects.mark_all_read(self.author)
        self.make_comment(self.commenter, "Second")
        self.assertEqual(Notification.objects.filter(recipient=self.author).count(), 2)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_in_app_preference_off_skips_notification(self, mock_send):
        NotificationPreference.objects.create(user=self.author, in_app_comment=False)
        self.make_comment(self.commenter, "Hello")
        self.assertFalse(Notification.objects.filter(recipient=self.author).exists())
        mock_send.assert_not_called()


class FollowNotificationSignalTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(email="user1@test.com", password="x", username="user1")
        self.user2 = User.objects.create_user(email="user2@test.com", password="x", username="user2")

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_follow_notification_created(self, mock_send):
        initial = Notification.objects.count()
        Follow.objects.create(follower=self.user2, following=self.user1)

        self.assertEqual(Notification.objects.count(), initial + 1)
        notification = Notification.objects.latest("created_at")
        self.assertEqual(notification.recipient, self.user1)
        self.assertEqual(notification.sender, self.user2)
        self.assertEqual(notification.notification_type, "follow")
        self.assertIn("started following you", notification.message)
        self.assertEqual(notification.content_object, self.user2)
        mock_send.assert_called_once_with(notification)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_follow_helper_and_refollow_do_not_duplicate(self, mock_send):
        self.user2.follow(self.user1)
        self.user2.unfollow(self.user1)
        self.user2.follow(self.user1)
        self.assertEqual(Notification.objects.filter(recipient=self.user1, notification_type="follow").count(), 1)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_self_follow_is_noop(self, mock_send):
        self.user1.follow(self.user1)
        self.assertFalse(Notification.objects.exists())
        mock_send.assert_not_called()

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_follow_preference_off(self, mock_send):
        NotificationPreference.objects.create(user=self.user1, in_app_follow=False)
        Follow.objects.create(follower=self.user2, following=self.user1)
        self.assertFalse(Notification.objects.exists())


class ArticlePublishedSignalTest(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(email="a@test.com", password="x", username="writer")
        self.follower1 = User.objects.create_user(email="f1@test.com", password="x", username="follower1")
        self.follower2 = User.objects.create_user(email="f2@test.com", password="x", username="follower2")
        Follow.objects.create(follower=self.follower1, following=self.author)
        Follow.objects.create(follower=self.follower2, following=self.author)
        Notification.objects.all().delete()  # drop the follow notifications
        self.category = Category.objects.create(name="Django", slug="django")

    def _article(self, status, **kwargs):
        return Article.objects.create(
            title=kwargs.pop("title", "Hello World"),
            author=self.author,
            category=self.category,
            content="body",
            status=status,
            **kwargs,
        )

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_published_article_notifies_followers(self, mock_send):
        article = self._article("published")

        notifications = Notification.objects.filter(notification_type="post", sender=self.author).order_by(
            "recipient__username"
        )
        self.assertEqual(notifications.count(), 2)
        self.assertEqual([n.recipient for n in notifications], [self.follower1, self.follower2])
        self.assertIn("published a new article", notifications[0].message)
        self.assertEqual(notifications[0].content_object, article)
        self.assertFalse(Notification.objects.filter(recipient=self.author).exists())
        self.assertEqual(mock_send.call_count, 2)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_draft_does_not_notify_until_published(self, mock_send):
        article = self._article("draft")
        self.assertFalse(Notification.objects.exists())
        mock_send.assert_not_called()

        article.status = "published"
        article.save()
        self.assertEqual(Notification.objects.filter(notification_type="post").count(), 2)
        self.assertEqual(mock_send.call_count, 2)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_resaving_published_article_does_not_duplicate(self, mock_send):
        article = self._article("published")
        article.title = "Edited title"
        article.save()
        article.views_count += 1
        article.save(update_fields=["views_count"])
        self.assertEqual(Notification.objects.filter(notification_type="post").count(), 2)
        self.assertEqual(mock_send.call_count, 2)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_unpublish_then_republish_after_read_notifies_again(self, mock_send):
        article = self._article("published")
        Notification.objects.mark_all_read(self.follower1)
        article.status = "draft"
        article.save()
        article.status = "published"
        article.save()
        # follower1 read theirs -> gets a fresh one; follower2 still has an unread one -> deduped
        self.assertEqual(Notification.objects.filter(recipient=self.follower1, notification_type="post").count(), 2)
        self.assertEqual(Notification.objects.filter(recipient=self.follower2, notification_type="post").count(), 1)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_follower_with_post_preference_off_is_skipped(self, mock_send):
        NotificationPreference.objects.create(user=self.follower1, in_app_post=False)
        self._article("published")
        self.assertFalse(Notification.objects.filter(recipient=self.follower1).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.follower2).exists())
        self.assertEqual(mock_send.call_count, 1)


@unittest.skipUnless(_optional_model("articles", "ArticleLike"), "ArticleLike model not available yet")
class ArticleLikeSignalTest(TestCase):
    """Runs once apps.articles.models.ArticleLike exists (wired lazily in AppConfig.ready)."""

    def setUp(self):
        self.ArticleLike = _optional_model("articles", "ArticleLike")
        # The articles app currently creates a 'like' Notification of its own in
        # apps/articles/signals.py; silence it so this test exercises the
        # notifications-app receiver (the intended single owner of this logic).
        try:
            from django.db.models.signals import post_save as _post_save

            from apps.articles.signals import article_like_post_save
        except ImportError:  # pragma: no cover
            pass
        else:
            if _post_save.disconnect(article_like_post_save, sender=self.ArticleLike):
                self.addCleanup(_post_save.connect, article_like_post_save, sender=self.ArticleLike)
        self.author = User.objects.create_user(email="a@test.com", password="x", username="writer")
        self.liker = User.objects.create_user(email="l@test.com", password="x", username="liker")
        self.article = Article.objects.create(title="Liked", author=self.author, content="body", status="published")

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_like_notifies_author(self, mock_send):
        self.ArticleLike.objects.create(user=self.liker, article=self.article)
        notification = Notification.objects.get(recipient=self.author, notification_type="like")
        self.assertEqual(notification.sender, self.liker)
        self.assertIn("liked your article", notification.message)
        mock_send.assert_called_once_with(notification)

    @patch("apps.notifications.signals.send_notification_to_user")
    def test_like_own_article_no_notification(self, mock_send):
        self.ArticleLike.objects.create(user=self.author, article=self.article)
        self.assertFalse(Notification.objects.filter(notification_type="like").exists())
        mock_send.assert_not_called()


class SendNotificationToUserTest(TestCase):
    """The channel-layer push helper."""

    def setUp(self):
        self.user1 = User.objects.create_user(email="ws-author@test.com", password="x", username="ws_author")
        self.user2 = User.objects.create_user(email="ws-actor@test.com", password="x", username="ws_actor")
        self.notification = Notification.objects.create(
            recipient=self.user1,
            sender=self.user2,
            notification_type="comment",
            message="Test notification",
        )

    @patch("channels.layers.get_channel_layer")
    def test_send_notification_calls_group_send(self, mock_get_channel_layer):
        from apps.notifications.consumers import user_group_name
        from apps.notifications.signals import send_notification_to_user

        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        send_notification_to_user(self.notification)

        self.assertEqual(mock_channel_layer.group_send.call_count, 2)
        calls = mock_channel_layer.group_send.call_args_list
        group_name = user_group_name(self.user1.pk)
        self.assertEqual(group_name, f"user_{self.user1.pk}")

        self.assertEqual(calls[0][0][0], group_name)
        self.assertEqual(calls[0][0][1]["type"], "notification_message")
        self.assertEqual(calls[0][0][1]["notification"]["message"], "Test notification")
        self.assertEqual(calls[0][0][1]["notification"]["sender"]["username"], "ws_actor")

        self.assertEqual(calls[1][0][0], group_name)
        self.assertEqual(calls[1][0][1]["type"], "unread_count_update")
        self.assertEqual(calls[1][0][1]["count"], 1)

    @patch("channels.layers.get_channel_layer")
    def test_send_notification_no_channel_layer(self, mock_get_channel_layer):
        from apps.notifications.signals import send_notification_to_user

        mock_get_channel_layer.return_value = None
        try:
            send_notification_to_user(self.notification)
        except Exception as exc:  # pragma: no cover
            self.fail(f"send_notification_to_user raised {exc!r}")

    @patch("channels.layers.get_channel_layer")
    def test_send_notification_swallows_layer_errors(self, mock_get_channel_layer):
        from apps.notifications.signals import send_notification_to_user

        layer = MagicMock()
        layer.group_send = AsyncMock(side_effect=RuntimeError("redis down"))
        mock_get_channel_layer.return_value = layer
        send_notification_to_user(self.notification)  # must not raise

    @patch("channels.layers.get_channel_layer")
    def test_push_disabled_in_profile_skips_websocket(self, mock_get_channel_layer):
        from apps.notifications.signals import send_notification_to_user

        layer = MagicMock()
        mock_get_channel_layer.return_value = layer
        self.user1.profile.push_notifications = False
        self.user1.profile.save()
        self.notification.refresh_from_db()

        send_notification_to_user(self.notification)
        layer.group_send.assert_not_called()

    def test_immediate_email_queued_when_digest_is_none(self):
        from django.core import mail

        from apps.notifications.signals import queue_notification_email

        NotificationPreference.objects.create(
            user=self.user1,
            digest_frequency="none",
            email_comment=True,
        )
        mail.outbox.clear()
        queue_notification_email(self.notification)  # Celery is eager in tests
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user1.email])
        self.assertIn("Test notification", mail.outbox[0].body)

    def test_no_immediate_email_with_daily_digest(self):
        from django.core import mail

        from apps.notifications.signals import queue_notification_email

        NotificationPreference.objects.create(user=self.user1, digest_frequency="daily", email_comment=True)
        mail.outbox.clear()
        queue_notification_email(self.notification)
        self.assertEqual(len(mail.outbox), 0)
