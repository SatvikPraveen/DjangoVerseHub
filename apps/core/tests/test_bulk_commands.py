# File: DjangoVerseHub/apps/core/tests/test_bulk_commands.py

from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.notifications.models import Notification

User = get_user_model()


class SendBulkNotificationsTests(TestCase):
    def setUp(self):
        self.active = User.objects.create_user(email="a@example.com", username="a", password="x")
        self.inactive = User.objects.create_user(email="i@example.com", username="i", password="x", is_active=False)

    def test_announcement_to_active_users(self):
        out = StringIO()
        call_command(
            "send_bulk_notifications",
            type="announcement",
            recipients="active",
            title="Maintenance",
            message="Tonight at 22:00 UTC",
            stdout=out,
        )
        notifications = Notification.objects.filter(recipient=self.active)
        self.assertEqual(notifications.count(), 1)
        note = notifications.get()
        self.assertIsNone(note.sender)
        self.assertEqual(note.notification_type, "system")
        self.assertEqual(note.message, "Maintenance: Tonight at 22:00 UTC")
        self.assertFalse(Notification.objects.filter(recipient=self.inactive).exists())

    def test_dry_run_creates_nothing(self):
        call_command(
            "send_bulk_notifications",
            type="announcement",
            recipients="all",
            title="T",
            message="M",
            dry_run=True,
            stdout=StringIO(),
        )
        self.assertEqual(Notification.objects.count(), 0)


class CleanupMediaTaskTests(TestCase):
    def test_task_runs_management_command(self):
        from apps.articles.tasks import cleanup_unused_media

        with mock.patch("django.core.management.call_command") as call:
            cleanup_unused_media(older_than_days=3)
        call.assert_called_once()
        self.assertEqual(call.call_args.args[0], "cleanup_unused_media")
        self.assertEqual(call.call_args.kwargs["older_than"], 3)
