# File: DjangoVerseHub/apps/notifications/tests/test_tasks.py
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification, NotificationPreference
from apps.notifications.tasks import (
    cleanup_old_notifications,
    send_daily_digest,
    send_notification,
    send_notification_email,
    send_weekly_digest,
)

User = get_user_model()


class DigestTaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="digest@test.com", password="x", username="digest", first_name="Dee")
        self.sender = User.objects.create_user(email="sender@test.com", password="x", username="sender")
        mail.outbox.clear()

    def make(self, user=None, age_hours=1, **kwargs):
        kwargs.setdefault("notification_type", "comment")
        kwargs.setdefault("message", "Someone commented on your article")
        n = Notification.objects.create(recipient=user or self.user, sender=self.sender, **kwargs)
        Notification.objects.filter(pk=n.pk).update(created_at=timezone.now() - timedelta(hours=age_hours))
        return n

    def test_daily_digest_emails_recent_unread(self):
        self.make(message="Fresh comment")
        self.make(message="Old comment", age_hours=48)  # outside the 24h window
        read = self.make(message="Read comment")
        read.mark_as_read()

        self.assertEqual(send_daily_digest(), 1)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ["digest@test.com"])
        self.assertIn("digest", email.subject.lower())
        self.assertIn("Fresh comment", email.body)
        self.assertNotIn("Old comment", email.body)
        self.assertNotIn("Read comment", email.body)
        self.assertIn("Hi Dee", email.body)
        self.assertIn("/notifications/", email.body)
        self.assertTrue(any("text/html" in alt for alt in email.alternatives))

    def test_no_email_without_unread(self):
        self.assertEqual(send_daily_digest(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_respects_profile_master_switch(self):
        self.make()
        self.user.profile.email_notifications = False
        self.user.profile.save()
        self.assertEqual(send_daily_digest(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_respects_digest_frequency(self):
        self.make()
        NotificationPreference.objects.create(user=self.user, digest_frequency="weekly")
        self.assertEqual(send_daily_digest(), 0)
        self.assertEqual(send_weekly_digest(), 1)

        NotificationPreference.objects.filter(user=self.user).update(digest_frequency="none")
        mail.outbox.clear()
        self.assertEqual(send_daily_digest(), 0)
        self.assertEqual(send_weekly_digest(), 0)

    def test_only_types_enabled_for_email_are_included(self):
        NotificationPreference.objects.create(user=self.user, email_comment=False, email_like=True)
        self.make(message="a comment", notification_type="comment")
        self.make(message="a like", notification_type="like")
        self.assertEqual(send_daily_digest(), 1)
        self.assertIn("a like", mail.outbox[0].body)
        self.assertNotIn("a comment", mail.outbox[0].body)

    def test_users_without_email_or_inactive_skipped(self):
        self.make()
        other = User.objects.create_user(email="inactive@test.com", password="x", username="inactive", is_active=False)
        self.make(user=other)
        self.assertEqual(send_daily_digest(), 1)

    def test_one_email_per_user(self):
        for i in range(5):
            self.make(message=f"msg {i}")
        second = User.objects.create_user(email="second@test.com", password="x", username="second")
        self.make(user=second)
        mail.outbox.clear()  # drop the welcome email sent on user creation
        self.assertEqual(send_daily_digest(), 2)
        self.assertEqual(len(mail.outbox), 2)


class ImmediateEmailTaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="now@test.com", password="x", username="now")
        self.notification = Notification.objects.create(
            recipient=self.user, notification_type="follow", message="X started following you."
        )
        mail.outbox.clear()

    def test_sends_when_allowed(self):
        NotificationPreference.objects.create(user=self.user, digest_frequency="none", email_follow=True)
        self.assertTrue(send_notification_email(self.notification.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("started following you", mail.outbox[0].body)

    def test_skips_when_type_disabled(self):
        NotificationPreference.objects.create(user=self.user, digest_frequency="none", email_follow=False)
        self.assertFalse(send_notification_email(self.notification.pk))
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_notification(self):
        self.assertFalse(send_notification_email(999999))
        self.assertFalse(send_notification(999999))


class CleanupTaskTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="clean@test.com", password="x", username="clean")

    def make(self, days_old, is_read, read_at_set=True):
        n = Notification.objects.create(recipient=self.user, notification_type="system", message="m")
        stamp = timezone.now() - timedelta(days=days_old)
        Notification.objects.filter(pk=n.pk).update(
            created_at=stamp,
            is_read=is_read,
            read_at=stamp if (is_read and read_at_set) else None,
        )
        return n

    def test_deletes_only_old_read_notifications(self):
        old_read = self.make(100, True)
        old_read_no_stamp = self.make(100, True, read_at_set=False)
        old_unread = self.make(100, False)
        recent_read = self.make(10, True)

        self.assertEqual(cleanup_old_notifications(), 2)
        remaining = set(Notification.objects.values_list("pk", flat=True))
        self.assertEqual(remaining, {old_unread.pk, recent_read.pk})
        self.assertNotIn(old_read.pk, remaining)
        self.assertNotIn(old_read_no_stamp.pk, remaining)

    def test_custom_window(self):
        self.make(10, True)
        self.assertEqual(cleanup_old_notifications(days=5), 1)
        self.assertEqual(Notification.objects.count(), 0)
