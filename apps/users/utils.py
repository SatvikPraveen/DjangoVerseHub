# File: DjangoVerseHub/apps/users/utils.py

import hashlib
import logging
import secrets

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core import signing
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------


def authenticate_by_identifier(request, identifier, password):
    """Authenticate with either an email address or a username.

    The default ModelBackend only understands USERNAME_FIELD (email), so a
    plain username is first resolved to the matching account's email.
    """
    from django.contrib.auth import authenticate

    from .models import CustomUser

    identifier = (identifier or "").strip()
    if not identifier or not password:
        return None

    email = identifier
    if "@" not in identifier:
        email = CustomUser.objects.filter(username__iexact=identifier).values_list("email", flat=True).first()
        if not email:
            return None

    return authenticate(request, **{CustomUser.USERNAME_FIELD: email, "password": password})


def get_user_ip(request):
    """Get user's IP address from request"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def get_client_info(request):
    """Get client information from request"""
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    # Basic user agent parsing
    info = {
        "user_agent": user_agent,
        "ip_address": get_user_ip(request),
        "is_mobile": "Mobile" in user_agent or "Android" in user_agent or "iPhone" in user_agent,
        "browser": "Unknown",
        "os": "Unknown",
    }

    # Simple browser detection
    if "Chrome" in user_agent:
        info["browser"] = "Chrome"
    elif "Firefox" in user_agent:
        info["browser"] = "Firefox"
    elif "Safari" in user_agent:
        info["browser"] = "Safari"
    elif "Edge" in user_agent:
        info["browser"] = "Edge"

    # Simple OS detection
    if "Windows" in user_agent:
        info["os"] = "Windows"
    elif "Mac" in user_agent:
        info["os"] = "MacOS"
    elif "Linux" in user_agent:
        info["os"] = "Linux"
    elif "Android" in user_agent:
        info["os"] = "Android"
    elif "iPhone" in user_agent or "iPad" in user_agent:
        info["os"] = "iOS"

    return info


# ---------------------------------------------------------------------------
# Signed, expiring tokens (email verification / password reset)
# ---------------------------------------------------------------------------

EMAIL_VERIFICATION_SALT = "users.email-verification"
EMAIL_VERIFICATION_MAX_AGE = 3 * 24 * 60 * 60  # 3 days

PASSWORD_RESET_SALT = "users.password-reset"
PASSWORD_RESET_MAX_AGE = 60 * 60  # 1 hour

RESEND_VERIFICATION_COOLDOWN = 10 * 60  # seconds


def _password_fingerprint(user):
    """Short digest of the password hash; changes whenever the password does."""
    return hashlib.sha256((user.password or "").encode()).hexdigest()[:16]


def build_absolute_url(path):
    """Prefix a site-relative path with settings.SITE_URL."""
    base = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
    return f"{base}{path}"


def make_email_verification_token(user):
    """Signed token binding the user to the email address being verified."""
    return signing.dumps({"uid": str(user.pk), "email": user.email}, salt=EMAIL_VERIFICATION_SALT)


def load_email_verification_token(token):
    """Return the user for `token`.

    Raises `signing.SignatureExpired` after 3 days and `signing.BadSignature`
    when the token is tampered with, refers to an unknown user, or the
    address on the account has changed since the token was issued.
    """
    from .models import CustomUser

    data = signing.loads(token, salt=EMAIL_VERIFICATION_SALT, max_age=EMAIL_VERIFICATION_MAX_AGE)
    user = CustomUser.objects.filter(pk=data.get("uid"), is_active=True).first()
    if user is None or user.email != data.get("email"):
        raise signing.BadSignature("Verification token does not match any account.")
    return user


def make_password_reset_token(user):
    """Signed token that becomes invalid as soon as the password changes."""
    return signing.dumps({"uid": str(user.pk), "pw": _password_fingerprint(user)}, salt=PASSWORD_RESET_SALT)


def load_password_reset_token(token):
    """Return the user for `token`; raises `signing.BadSignature` (or `SignatureExpired`)."""
    from .models import CustomUser

    data = signing.loads(token, salt=PASSWORD_RESET_SALT, max_age=PASSWORD_RESET_MAX_AGE)
    user = CustomUser.objects.filter(pk=data.get("uid"), is_active=True).first()
    if user is None or _password_fingerprint(user) != data.get("pw"):
        raise signing.BadSignature("Password reset token is no longer valid.")
    return user


def resend_verification_cache_key(user):
    return f"users:resend-verification:{user.pk}"


# ---------------------------------------------------------------------------
# Transactional email (queued through Celery; broker errors never propagate)
# ---------------------------------------------------------------------------


def _queue(task, *args):
    try:
        task.delay(*args)
    except Exception as exc:  # noqa: BLE001 - broker/connection errors
        logger.warning("Could not queue %s: %s", task.name, exc)
        return False
    return True


def send_verification_email(user):
    """Queue the email-verification message for `user`. Returns True if queued."""
    if not user.email:
        return False

    from .tasks import send_email_verification

    token = make_email_verification_token(user)
    url = build_absolute_url(reverse("users:verify_email", kwargs={"token": token}))
    return _queue(send_email_verification, str(user.pk), url)


def send_password_reset_email(user):
    """Queue the password-reset message for `user`. Returns True if queued."""
    if not user.email:
        return False

    from .tasks import send_password_reset_email as task

    token = make_password_reset_token(user)
    url = build_absolute_url(reverse("users:password_reset_confirm", kwargs={"token": token}))
    return _queue(task, str(user.pk), url)


# ---------------------------------------------------------------------------
# GDPR: data export
# ---------------------------------------------------------------------------


def _profile_data(profile):
    if profile is None:
        return None
    return {
        "full_name": profile.full_name,
        "bio": profile.bio,
        "avatar": profile.avatar.name if profile.avatar else None,
        "cover_image": profile.cover_image.name if profile.cover_image else None,
        "gender": profile.gender,
        "location": profile.location,
        "website": profile.website,
        "twitter": profile.twitter,
        "linkedin": profile.linkedin,
        "github": profile.github,
        "theme": profile.theme,
        "timezone": profile.timezone,
        "language": profile.language,
        "is_public": profile.is_public,
        "show_email": profile.show_email,
        "show_real_name": profile.show_real_name,
        "email_notifications": profile.email_notifications,
        "push_notifications": profile.push_notifications,
        "marketing_emails": profile.marketing_emails,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def build_user_export(user):
    """Everything the platform stores about `user`, as a JSON-serialisable dict.

    Only the public model APIs of the other apps are used; nothing is modified.
    Serialise with `django.core.serializers.json.DjangoJSONEncoder` (UUIDs, datetimes).
    """
    from apps.articles.models import Article, ArticleLike, Bookmark
    from apps.comments.models import Comment, CommentLike
    from apps.notifications.models import Notification

    from .models import Follow

    profile = getattr(user, "profile", None)

    articles = [
        {
            "id": a.id,
            "title": a.title,
            "slug": a.slug,
            "status": a.status,
            "summary": a.summary,
            "content": a.content,
            "created_at": a.created_at,
            "updated_at": a.updated_at,
            "published_at": a.published_at,
        }
        for a in Article.objects.filter(author=user).order_by("created_at")
    ]

    comments = [
        {
            "id": c.id,
            "content": c.content,
            "target_type": c.content_type.model,
            "target_id": c.object_id,
            "parent_id": c.parent_id,
            "is_active": c.is_active,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        }
        for c in Comment.objects.filter(author=user).select_related("content_type").order_by("created_at")
    ]

    likes = {
        "articles": [
            {"article_id": like.article_id, "title": like.article.title, "created_at": like.created_at}
            for like in ArticleLike.objects.filter(user=user).select_related("article").order_by("created_at")
        ],
        "comments": [
            {"comment_id": like.comment_id, "created_at": like.created_at}
            for like in CommentLike.objects.filter(user=user).order_by("created_at")
        ],
    }

    bookmarks = [
        {"article_id": b.article_id, "title": b.article.title, "slug": b.article.slug, "created_at": b.created_at}
        for b in Bookmark.objects.filter(user=user).select_related("article").order_by("created_at")
    ]

    follows = {
        "following": [
            {"user_id": f.following_id, "username": f.following.username, "since": f.created_at}
            for f in Follow.objects.filter(follower=user).select_related("following").order_by("created_at")
        ],
        "followers": [
            {"user_id": f.follower_id, "username": f.follower.username, "since": f.created_at}
            for f in Follow.objects.filter(following=user).select_related("follower").order_by("created_at")
        ],
    }

    notifications = [
        {
            "id": n.id,
            "type": n.notification_type,
            "message": n.message,
            "sender": n.sender.username if n.sender else None,
            "is_read": n.is_read,
            "created_at": n.created_at,
            "read_at": n.read_at,
        }
        for n in Notification.objects.filter(recipient=user).select_related("sender").order_by("created_at")
    ]

    return {
        "exported_at": timezone.now(),
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "date_of_birth": user.date_of_birth,
            "email_verified": user.email_verified,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "login_count": user.login_count,
        },
        "profile": _profile_data(profile),
        "articles": articles,
        "comments": comments,
        "likes": likes,
        "bookmarks": bookmarks,
        "follows": follows,
        "notifications": notifications,
    }


# ---------------------------------------------------------------------------
# GDPR: account deletion / anonymisation
# ---------------------------------------------------------------------------

ANONYMISED_EMAIL_DOMAIN = "deleted.invalid"


def has_published_content(user):
    from apps.articles.models import Article

    return Article.objects.filter(author=user, status="published").exists()


def _expire_user_sessions(user):
    """Best-effort removal of DB-backed sessions for `user`.

    Independently of this sweep, every session is rejected on the next request
    because the password hash changes (session auth hash) and `is_active` is False.
    """
    if "django.contrib.sessions" not in settings.INSTALLED_APPS:
        return
    uid = str(user.pk)
    try:
        for session in Session.objects.filter(expire_date__gte=timezone.now()).iterator():
            if session.get_decoded().get("_auth_user_id") == uid:
                session.delete()
    except Exception as exc:  # noqa: BLE001 - table absent / cache-backed sessions
        logger.debug("Session sweep skipped for %s: %s", user.pk, exc)


def anonymise_user(user):
    """Scrub personal data from `user` while keeping their published content.

    The row survives so article/comment attribution stays consistent, but the
    account can never be used again: unusable password, inactive, API tokens and
    sessions revoked, and everything identifying replaced or cleared.
    """
    from rest_framework.authtoken.models import Token

    from apps.articles.models import Article, ArticleLike, Bookmark
    from apps.notifications.models import Notification

    from .models import Follow

    suffix = secrets.token_hex(4)  # 8 hex characters
    user.username = f"deleted-{suffix}"
    user.email = f"deleted-{suffix}@{ANONYMISED_EMAIL_DOMAIN}"
    user.first_name = ""
    user.last_name = ""
    user.phone_number = ""
    user.date_of_birth = None
    user.last_login_ip = None
    user.email_verified = False
    user.is_active = False
    user.is_staff = False
    user.is_superuser = False
    user.set_unusable_password()
    user.save()

    profile = getattr(user, "profile", None)
    if profile is not None:
        if profile.avatar:
            profile.avatar.delete(save=False)
        if profile.cover_image:
            profile.cover_image.delete(save=False)
        for field in ("full_name", "bio", "gender", "location", "website", "twitter", "linkedin", "github"):
            setattr(profile, field, "")
        profile.is_public = False
        profile.show_email = False
        profile.email_notifications = False
        profile.push_notifications = False
        profile.marketing_emails = False
        profile.save()

    # Personal, non-content data goes; published (and archived) articles and comments stay.
    Article.objects.filter(author=user, status="draft").delete()
    ArticleLike.objects.filter(user=user).delete()
    Bookmark.objects.filter(user=user).delete()
    Follow.objects.filter(follower=user).delete()
    Follow.objects.filter(following=user).delete()
    Notification.objects.filter(recipient=user).delete()

    Token.objects.filter(user=user).delete()
    _expire_user_sessions(user)
    return user


def delete_or_anonymise_user(user):
    """Remove `user`'s account. Returns "anonymised" or "deleted".

    Accounts with published articles are anonymised so the articles remain
    readable; everything else is hard-deleted (cascades remove the rest).
    """
    if has_published_content(user):
        anonymise_user(user)
        logger.info("Anonymised account %s", user.pk)
        return "anonymised"

    from rest_framework.authtoken.models import Token

    Token.objects.filter(user=user).delete()
    _expire_user_sessions(user)
    pk = user.pk
    user.delete()
    logger.info("Deleted account %s", pk)
    return "deleted"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class UserStatsCalculator:
    """Calculate various user statistics"""

    @staticmethod
    def get_user_activity_stats(user, days=30):
        """Get user activity statistics for specified days"""
        return {
            "login_count": user.login_count,
            "profile_views": 0,  # Would track in separate model
            "content_created": 0,  # Would count articles, comments, etc.
            "last_active": user.last_login,
            "activity_score": 0,  # Calculated activity score
        }

    @staticmethod
    def calculate_profile_completion(profile):
        """Calculate profile completion percentage"""
        fields = ["full_name", "bio", "avatar", "location", "website", "twitter", "linkedin", "github"]

        completed = 0
        for field in fields:
            if getattr(profile, field, None):
                completed += 1

        # Add user fields
        user_fields = ["first_name", "last_name", "phone_number", "date_of_birth"]
        for field in user_fields:
            if getattr(profile.user, field, None):
                completed += 1

        total_fields = len(fields) + len(user_fields)
        return (completed / total_fields) * 100
