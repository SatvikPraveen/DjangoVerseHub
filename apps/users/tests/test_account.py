# File: DjangoVerseHub/apps/users/tests/test_account.py
"""Email verification, password reset, data export and account deletion."""

import json
import re
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from apps.articles.models import Article, ArticleLike, Bookmark
from apps.comments.models import Comment, CommentLike
from apps.notifications.models import Notification

from ..models import Follow
from ..utils import (
    EMAIL_VERIFICATION_MAX_AGE,
    PASSWORD_RESET_MAX_AGE,
    build_user_export,
    make_email_verification_token,
    make_password_reset_token,
    resend_verification_cache_key,
)

User = get_user_model()

SITE = "https://hub.example.com"


def _verify_link(body):
    match = re.search(r"https?://\S+/users/verify-email/\S+/", body)
    assert match, body
    return match.group(0)


def _reset_link(body):
    match = re.search(r"https?://\S+/users/password-reset/confirm/\S+/", body)
    assert match, body
    return match.group(0)


@override_settings(SITE_URL=SITE)
class EmailVerificationTest(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []
        self.client = Client()
        self.user = User.objects.create_user(email="verify@example.com", username="verifyme", password="testpass123")
        mail.outbox = []  # drop the welcome email

    # -- signup -----------------------------------------------------------

    def test_signup_queues_verification_email_after_commit(self):
        data = {
            "email": "fresh@example.com",
            "username": "fresh",
            "password1": "complexpass123",
            "password2": "complexpass123",
            "terms_accepted": True,
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("users:signup"), data)
        self.assertEqual(response.status_code, 302)

        verification = [m for m in mail.outbox if "Verify" in m.subject]
        self.assertEqual(len(verification), 1)
        self.assertEqual(verification[0].to, ["fresh@example.com"])
        link = _verify_link(verification[0].body)
        self.assertTrue(link.startswith(f"{SITE}/users/verify-email/"))

        # The link works and marks the (new, logged-in) user verified.
        response = self.client.get(link, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.get(email="fresh@example.com").email_verified)

    def test_signup_survives_broker_outage(self):
        data = {
            "email": "nobroker@example.com",
            "username": "nobroker",
            "password1": "complexpass123",
            "password2": "complexpass123",
            "terms_accepted": True,
        }
        with (
            patch("apps.users.tasks.send_email_verification.delay", side_effect=ConnectionError("down")),
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(reverse("users:signup"), data)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="nobroker@example.com").exists())

    def test_api_register_queues_verification_email(self):
        data = {
            "email": "apiuser@example.com",
            "username": "apiuser",
            "password": "complexpass123",
            "password_confirm": "complexpass123",
        }
        with self.captureOnCommitCallbacks(execute=True):
            response = APIClient().post(reverse("users:user-register"), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(any("Verify" in m.subject for m in mail.outbox))

    # -- verify link ------------------------------------------------------

    def test_valid_token_marks_email_verified(self):
        token = make_email_verification_token(self.user)
        response = self.client.get(reverse("users:verify_email", kwargs={"token": token}))

        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_valid_token_logged_in_redirects_to_settings(self):
        self.client.force_login(self.user)
        token = make_email_verification_token(self.user)
        response = self.client.get(reverse("users:verify_email", kwargs={"token": token}), follow=True)

        self.assertRedirects(response, reverse("users:settings"))
        self.assertContains(response, "has been verified")
        self.assertNotContains(response, "Resend verification email")

    def test_already_verified_token_is_harmless(self):
        self.user.email_verified = True
        self.user.save()
        token = make_email_verification_token(self.user)
        response = self.client.get(reverse("users:verify_email", kwargs={"token": token}), follow=True)
        self.assertContains(response, "already verified")

    def test_tampered_token_shows_friendly_page(self):
        token = make_email_verification_token(self.user) + "x"
        response = self.client.get(reverse("users:verify_email", kwargs={"token": token}))

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "isn't valid", status_code=400)
        self.assertContains(response, "Sign in to request", status_code=400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_invalid_token_offers_resend_when_logged_in(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:verify_email", kwargs={"token": "garbage"}))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, reverse("users:resend_verification"), status_code=400)

    def test_expired_token(self):
        token = make_email_verification_token(self.user)
        future = time.time() + EMAIL_VERIFICATION_MAX_AGE + 60
        with patch("django.core.signing.time.time", return_value=future):
            response = self.client.get(reverse("users:verify_email", kwargs={"token": token}))

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "expired", status_code=400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.email_verified)

    def test_token_bound_to_email_at_issue_time(self):
        token = make_email_verification_token(self.user)
        self.user.email = "changed@example.com"
        self.user.save()
        response = self.client.get(reverse("users:verify_email", kwargs={"token": token}))
        self.assertEqual(response.status_code, 400)

    def test_verification_token_not_usable_for_password_reset(self):
        token = make_email_verification_token(self.user)
        response = self.client.get(reverse("users:password_reset_confirm", kwargs={"token": token}))
        self.assertEqual(response.status_code, 400)

    # -- resend -----------------------------------------------------------

    def test_resend_requires_login_and_post(self):
        response = self.client.post(reverse("users:resend_verification"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response["Location"])

        self.client.force_login(self.user)
        response = self.client.get(reverse("users:resend_verification"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(mail.outbox, [])

    def test_resend_sends_and_is_throttled(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:resend_verification"), follow=True)
        self.assertRedirects(response, reverse("users:settings"))
        self.assertContains(response, "sent a new verification link")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIsNotNone(cache.get(resend_verification_cache_key(self.user)))

        response = self.client.post(reverse("users:resend_verification"), follow=True)
        self.assertContains(response, "wait 10 minutes")
        self.assertEqual(len(mail.outbox), 1)

        # Once the cooldown lapses a new email goes out.
        cache.delete(resend_verification_cache_key(self.user))
        self.client.post(reverse("users:resend_verification"))
        self.assertEqual(len(mail.outbox), 2)

    def test_resend_throttle_is_per_user(self):
        other = User.objects.create_user(email="other@example.com", username="other", password="testpass123")
        mail.outbox = []
        self.client.force_login(self.user)
        self.client.post(reverse("users:resend_verification"))
        self.client.force_login(other)
        self.client.post(reverse("users:resend_verification"))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["other@example.com", "verify@example.com"])

    def test_resend_noop_when_verified(self):
        self.user.email_verified = True
        self.user.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse("users:resend_verification"), follow=True)
        self.assertContains(response, "already verified")
        self.assertEqual(mail.outbox, [])

    # -- banner + API ----------------------------------------------------------

    def test_banner_on_settings_and_own_profile_until_verified(self):
        self.client.force_login(self.user)
        for url in (reverse("users:settings"), reverse("users:profile", kwargs={"pk": self.user.pk})):
            response = self.client.get(url)
            self.assertContains(response, 'id="verify-email-banner"')
            self.assertContains(response, reverse("users:resend_verification"))

        self.user.email_verified = True
        self.user.save()
        for url in (reverse("users:settings"), reverse("users:profile", kwargs={"pk": self.user.pk})):
            self.assertNotContains(self.client.get(url), 'id="verify-email-banner"')

    def test_banner_not_shown_on_someone_elses_profile(self):
        other = User.objects.create_user(email="other@example.com", username="other", password="testpass123")
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:profile", kwargs={"pk": other.pk}))
        self.assertNotContains(response, 'id="verify-email-banner"')

    def test_unverified_user_can_still_log_in(self):
        response = self.client.post(
            reverse("users:login"), {"username": "verify@example.com", "password": "testpass123"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_api_me_exposes_email_verified(self):
        api = APIClient()
        api.force_authenticate(self.user)
        self.assertIs(api.get(reverse("users:user-me")).data["email_verified"], False)

        self.user.email_verified = True
        self.user.save()
        self.assertIs(api.get(reverse("users:user-me")).data["email_verified"], True)

        # ...but not to other people.
        other = User.objects.create_user(email="other@example.com", username="other", password="testpass123")
        api.force_authenticate(other)
        response = api.get(reverse("users:user-detail", kwargs={"pk": self.user.pk}))
        self.assertNotIn("email_verified", response.data)


@override_settings(SITE_URL=SITE)
class PasswordResetTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(email="reset@example.com", username="resetme", password="oldpass123")
        mail.outbox = []

    def test_form_renders(self):
        response = self.client.get(reverse("users:password_reset"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Send Reset Link")

    def test_login_page_links_to_reset(self):
        self.assertContains(self.client.get(reverse("users:login")), reverse("users:password_reset"))

    def test_authenticated_user_is_redirected(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:password_reset"))
        self.assertRedirects(response, reverse("users:settings"), fetch_redirect_response=False)

    def test_same_response_whether_or_not_email_exists(self):
        known = self.client.post(reverse("users:password_reset"), {"email": "RESET@example.com"})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reset@example.com"])
        self.assertTrue(_reset_link(mail.outbox[0].body).startswith(f"{SITE}/users/password-reset/confirm/"))

        unknown = self.client.post(reverse("users:password_reset"), {"email": "nobody@example.com"})
        self.assertEqual(len(mail.outbox), 1)

        self.assertEqual((known.status_code, known["Location"]), (unknown.status_code, unknown["Location"]))
        self.assertRedirects(unknown, reverse("users:login"), fetch_redirect_response=False)
        followed = self.client.post(reverse("users:password_reset"), {"email": "nobody@example.com"}, follow=True)
        self.assertContains(followed, "If an account exists")

    def test_inactive_user_gets_no_email(self):
        self.user.is_active = False
        self.user.save()
        self.client.post(reverse("users:password_reset"), {"email": self.user.email})
        self.assertEqual(mail.outbox, [])

    def test_invalid_email_reshows_form(self):
        response = self.client.post(reverse("users:password_reset"), {"email": "not-an-email"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_broker_outage_does_not_break_request(self):
        with patch("apps.users.tasks.send_password_reset_email.delay", side_effect=ConnectionError("down")):
            response = self.client.post(reverse("users:password_reset"), {"email": self.user.email})
        self.assertEqual(response.status_code, 302)

    def test_full_reset_flow(self):
        self.client.post(reverse("users:password_reset"), {"email": self.user.email})
        link = _reset_link(mail.outbox[0].body)
        path = link[len(SITE) :]

        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a new password")

        response = self.client.post(path, {"new_password1": "brandnewpass456", "new_password2": "brandnewpass456"})
        self.assertRedirects(response, reverse("users:login"), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("brandnewpass456"))

        # The link is single-use: the password fingerprint changed.
        response = self.client.get(path)
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "isn't valid", status_code=400)

        # And the new password works.
        self.assertTrue(self.client.login(username="reset@example.com", password="brandnewpass456"))

    def test_mismatched_passwords_reshow_form(self):
        token = make_password_reset_token(self.user)
        url = reverse("users:password_reset_confirm", kwargs={"token": token})
        response = self.client.post(url, {"new_password1": "brandnewpass456", "new_password2": "different456"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "match")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("oldpass123"))

    def test_tampered_and_expired_tokens(self):
        token = make_password_reset_token(self.user)
        response = self.client.get(reverse("users:password_reset_confirm", kwargs={"token": token + "x"}))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, reverse("users:password_reset"), status_code=400)

        future = time.time() + PASSWORD_RESET_MAX_AGE + 60
        with patch("django.core.signing.time.time", return_value=future):
            response = self.client.get(reverse("users:password_reset_confirm", kwargs={"token": token}))
        self.assertEqual(response.status_code, 400)

    def test_reset_token_rejects_email_verification_salt(self):
        token = make_password_reset_token(self.user)
        with self.assertRaises(signing.BadSignature):
            signing.loads(token, salt="users.email-verification")


class _ContentMixin:
    """Build a user with one of everything the export/deletion code touches."""

    def make_content(self, user, published=True):
        other = User.objects.create_user(email=f"peer-{user.username}@example.com", username=f"peer-{user.username}")
        article = Article.objects.create(
            title="My Article", content="Body " * 30, author=user, status="published" if published else "draft"
        )
        draft = Article.objects.create(title="My Draft", content="Draft body", author=user, status="draft")
        peer_article = Article.objects.create(
            title="Peer Article", content="Peer body", author=other, status="published"
        )
        comment = Comment.objects.create(author=user, content="Nice one", content_object=peer_article)
        peer_comment = Comment.objects.create(author=other, content="Thanks", content_object=peer_article)
        ArticleLike.objects.create(user=user, article=peer_article)
        CommentLike.objects.create(user=user, comment=peer_comment)
        Bookmark.objects.create(user=user, article=peer_article)
        Follow.objects.create(follower=user, following=other)
        Follow.objects.create(follower=other, following=user)
        Notification.objects.create(recipient=user, sender=other, notification_type="system", message="Hello")
        return {
            "other": other,
            "article": article,
            "draft": draft,
            "peer_article": peer_article,
            "comment": comment,
            "peer_comment": peer_comment,
        }


class DataExportTest(_ContentMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="export@example.com", username="exporter", password="testpass123", first_name="Ex"
        )
        self.user.profile.bio = "About me"
        self.user.profile.save()
        self.content = self.make_content(self.user)

    def test_build_user_export_contents(self):
        data = build_user_export(self.user)
        # Must round-trip through JSON with Django's encoder (UUIDs, datetimes).
        json.dumps(data, cls=DjangoJSONEncoder)

        self.assertEqual(data["user"]["email"], "export@example.com")
        self.assertEqual(data["user"]["first_name"], "Ex")
        self.assertEqual(data["profile"]["bio"], "About me")

        titles = {a["title"]: a for a in data["articles"]}
        self.assertEqual(set(titles), {"My Article", "My Draft"})
        for key in ("id", "title", "slug", "status", "content", "created_at", "updated_at", "published_at"):
            self.assertIn(key, titles["My Article"])
        self.assertEqual(titles["My Article"]["status"], "published")

        self.assertEqual([c["content"] for c in data["comments"]], ["Nice one"])
        self.assertEqual(data["comments"][0]["target_id"], self.content["peer_article"].id)
        self.assertEqual([like["title"] for like in data["likes"]["articles"]], ["Peer Article"])
        self.assertEqual([like["comment_id"] for like in data["likes"]["comments"]], [self.content["peer_comment"].id])
        self.assertEqual([b["title"] for b in data["bookmarks"]], ["Peer Article"])
        self.assertEqual([f["username"] for f in data["follows"]["following"]], ["peer-exporter"])
        self.assertEqual([f["username"] for f in data["follows"]["followers"]], ["peer-exporter"])
        # The notifications app also creates follow/comment notifications through signals.
        system = [n for n in data["notifications"] if n["type"] == "system"]
        self.assertEqual([(n["message"], n["sender"]) for n in system], [("Hello", "peer-exporter")])
        self.assertTrue(all(n["sender"] == "peer-exporter" for n in data["notifications"]))

    def test_export_excludes_other_users_data(self):
        data = build_user_export(self.content["other"])
        self.assertEqual([a["title"] for a in data["articles"]], ["Peer Article"])
        self.assertEqual([c["content"] for c in data["comments"]], ["Thanks"])
        self.assertEqual(data["likes"]["articles"], [])
        self.assertEqual(data["bookmarks"], [])
        # Only notifications *received* by this user (all sent by the exporter through signals).
        self.assertTrue(data["notifications"])
        self.assertTrue(all(n["sender"] == "exporter" for n in data["notifications"]))
        self.assertFalse(any(n["message"] == "Hello" for n in data["notifications"]))

    def test_export_view_requires_login_and_post(self):
        response = self.client.post(reverse("users:export_data"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response["Location"])

        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("users:export_data")).status_code, 405)

    def test_export_view_returns_json_attachment(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("users:export_data"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertIn('attachment; filename="djangoversehub-export-exporter-', response["Content-Disposition"])
        payload = json.loads(response.content)
        self.assertEqual(payload["user"]["username"], "exporter")
        self.assertEqual(len(payload["articles"]), 2)
        self.assertEqual(payload["articles"][0]["id"], str(self.content["article"].id))

    def test_settings_page_links_export_and_delete(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:settings"))
        self.assertContains(response, reverse("users:export_data"))
        self.assertContains(response, reverse("users:delete_account"))

    def test_api_me_export(self):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION="Token " + Token.objects.create(user=self.user).key)
        response = api.get(reverse("users:user-export"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertEqual(response.data["user"]["username"], "exporter")
        self.assertEqual(len(response.data["articles"]), 2)
        self.assertEqual(response.data["comments"][0]["content"], "Nice one")

    def test_api_me_export_requires_auth(self):
        self.assertEqual(APIClient().get(reverse("users:user-export")).status_code, 401)


class AccountDeletionTest(_ContentMixin, TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email="bye@example.com", username="leaver", password="testpass123", first_name="Bye", last_name="Now"
        )
        self.user.profile.full_name = "Bye Now"
        self.user.profile.bio = "Leaving"
        self.user.profile.save()

    def test_confirm_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("users:delete_account"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delete my account")
        self.assertContains(response, "permanently deleted")

        self.make_content(self.user)
        response = self.client.get(reverse("users:delete_account"))
        self.assertContains(response, "Close my account")
        self.assertContains(response, "anonymised")

    def test_requires_login(self):
        response = self.client.get(reverse("users:delete_account"))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse("users:delete_account"), {"password": "testpass123"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("users:delete_account"), {"password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "password is incorrect")
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_hard_delete_without_published_articles(self):
        content = self.make_content(self.user, published=False)
        Token.objects.create(user=self.user)
        self.client.force_login(self.user)

        response = self.client.post(reverse("users:delete_account"), {"password": "testpass123"}, follow=True)
        self.assertRedirects(response, reverse("users:login"))
        self.assertContains(response, "all of its data have been deleted")

        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertFalse(Article.objects.filter(pk=content["article"].pk).exists())
        self.assertFalse(Comment.objects.filter(pk=content["comment"].pk).exists())
        self.assertFalse(Token.objects.filter(user_id=self.user.pk).exists())
        # Other people's content is untouched.
        self.assertTrue(Article.objects.filter(pk=content["peer_article"].pk).exists())
        self.assertTrue(User.objects.filter(pk=content["other"].pk).exists())

    def test_anonymise_with_published_articles(self):
        content = self.make_content(self.user, published=True)
        token = Token.objects.create(user=self.user)
        self.client.force_login(self.user)
        original_email = self.user.email

        response = self.client.post(reverse("users:delete_account"), {"password": "testpass123"}, follow=True)
        self.assertRedirects(response, reverse("users:login"))
        self.assertContains(response, "published articles remain")
        self.assertNotIn("_auth_user_id", self.client.session)

        user = User.objects.get(pk=self.user.pk)
        self.assertRegex(user.username, r"^deleted-[0-9a-f]{8}$")
        self.assertRegex(user.email, r"^deleted-[0-9a-f]{8}@deleted\.invalid$")
        self.assertEqual(user.username[8:], user.email.split("@")[0][8:])
        self.assertEqual((user.first_name, user.last_name), ("", ""))
        self.assertFalse(user.is_active)
        self.assertFalse(user.email_verified)
        self.assertFalse(user.has_usable_password())
        self.assertEqual((user.profile.full_name, user.profile.bio), ("", ""))
        self.assertFalse(user.profile.is_public)

        # Tokens and sessions are gone; the account cannot be used again.
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertFalse(self.client.login(username=original_email, password="testpass123"))
        self.assertFalse(User.objects.filter(email=original_email).exists())

        # Published content stays (re-attributed); personal traces go.
        article = Article.objects.get(pk=content["article"].pk)
        self.assertEqual(article.author_id, user.pk)
        self.assertTrue(Comment.objects.filter(pk=content["comment"].pk).exists())
        self.assertFalse(Article.objects.filter(pk=content["draft"].pk).exists())
        self.assertFalse(ArticleLike.objects.filter(user=user).exists())
        self.assertFalse(Bookmark.objects.filter(user=user).exists())
        self.assertFalse(Follow.objects.filter(follower=user).exists())
        self.assertFalse(Follow.objects.filter(following=user).exists())
        self.assertFalse(Notification.objects.filter(recipient=user).exists())

        # Anonymised accounts are invisible in listings and their profile 404s.
        self.assertEqual(self.client.get(reverse("users:profile", kwargs={"pk": user.pk})).status_code, 404)

    def test_anonymised_user_invalidates_existing_sessions(self):
        self.make_content(self.user, published=True)
        other_browser = Client()
        other_browser.force_login(self.user)
        self.client.force_login(self.user)

        self.client.post(reverse("users:delete_account"), {"password": "testpass123"})

        response = other_browser.get(reverse("users:settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response["Location"])


class AccountDeletionAPITest(_ContentMixin, TestCase):
    def setUp(self):
        self.api = APIClient()
        self.user = User.objects.create_user(email="api-bye@example.com", username="apileaver", password="testpass123")
        self.token = Token.objects.create(user=self.user)
        self.api.credentials(HTTP_AUTHORIZATION="Token " + self.token.key)
        self.url = reverse("users:user-me")

    def test_requires_auth(self):
        response = APIClient().delete(self.url, {"password": "testpass123"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_password_required_and_checked(self):
        response = self.api.delete(self.url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.api.delete(self.url, {"password": "wrong"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        errors = response.data.get("error", {}).get("details", response.data)
        self.assertIn("password", errors)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_hard_delete(self):
        self.make_content(self.user, published=False)
        response = self.api.delete(self.url, {"password": "testpass123"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["outcome"], "deleted")
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

    def test_anonymise(self):
        content = self.make_content(self.user, published=True)
        response = self.api.delete(self.url, {"password": "testpass123"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["outcome"], "anonymised")
        user = User.objects.get(pk=self.user.pk)
        self.assertRegex(user.username, r"^deleted-[0-9a-f]{8}$")
        self.assertFalse(user.is_active)
        self.assertEqual(Article.objects.get(pk=content["article"].pk).author_id, user.pk)
        self.assertFalse(Token.objects.filter(key=self.token.key).exists())

        # The old token no longer authenticates.
        self.assertEqual(self.api.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED)
