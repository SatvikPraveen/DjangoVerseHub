# File: DjangoVerseHub/apps/users/views.py

import logging

from django.apps import apps
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import redirect_to_login
from django.core import signing
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import DetailView, ListView, UpdateView
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response

from .forms import (
    CustomLoginForm,
    CustomUserCreationForm,
    DeleteAccountForm,
    PasswordChangeForm,
    PasswordResetRequestForm,
    ProfileForm,
    UserUpdateForm,
)
from .models import CustomUser, Profile
from .serializers import (
    AccountDeletionSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    PublicProfileSerializer,
    UserListSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .utils import (
    RESEND_VERIFICATION_COOLDOWN,
    build_user_export,
    delete_or_anonymise_user,
    get_client_info,
    has_published_content,
    load_email_verification_token,
    load_password_reset_token,
    resend_verification_cache_key,
    send_password_reset_email,
    send_verification_email,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _article_model():
    return apps.get_model("articles", "Article")


def _comment_model():
    return apps.get_model("comments", "Comment")


def _safe_redirect_target(request, candidate, fallback):
    """Return `candidate` if it is a safe local URL, else `fallback`."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _wants_json(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get(
        "accept", ""
    )


def _published_articles_for(user):
    return _article_model().objects.filter(author=user, status="published")


def _user_activity(user, limit=20):
    """Merge a user's recent articles and comments into one timeline."""
    Article = _article_model()
    Comment = _comment_model()

    articles = list(Article.objects.filter(author=user).select_related("category").order_by("-created_at")[:limit])
    comments = list(
        Comment.objects.filter(author=user, is_active=True)
        .select_related("content_type")
        .prefetch_related("content_object")
        .order_by("-created_at")[:limit]
    )

    timeline = []
    for article in articles:
        timeline.append(
            {
                "type": "article_published" if article.status == "published" else "article_created",
                "description": (
                    f'Published "{article.title}"' if article.status == "published" else f'Drafted "{article.title}"'
                ),
                "created_at": article.created_at,
                "object": article,
            }
        )
    for comment in comments:
        target = getattr(comment.content_object, "title", None) or "a post"
        timeline.append(
            {
                "type": "comment_posted",
                "description": f'Commented on "{target}"',
                "created_at": comment.created_at,
                "object": comment,
            }
        )

    timeline.sort(key=lambda item: item["created_at"], reverse=True)
    return articles, comments, timeline[:limit]


# ---------------------------------------------------------------------------
# Web Views
# ---------------------------------------------------------------------------


def signup_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect("users:profile", pk=request.user.pk)

    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            client_info = get_client_info(request)
            user.update_login_stats(client_info["ip_address"])

            transaction.on_commit(lambda: send_verification_email(user))

            messages.success(
                request,
                "Account created successfully! Welcome aboard! We've sent a link to verify your email address.",
            )
            return redirect("users:profile", pk=user.pk)
    else:
        form = CustomUserCreationForm()

    return render(request, "users/signup.html", {"form": form})


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect("users:profile", pk=request.user.pk)

    if request.method == "POST":
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            client_info = get_client_info(request)
            user.update_login_stats(client_info["ip_address"])

            if form.cleaned_data.get("remember_me"):
                request.session.set_expiry(1209600)  # 2 weeks

            messages.success(request, f"Welcome back, {user.get_short_name()}!")

            next_url = request.POST.get("next") or request.GET.get("next")
            return redirect(_safe_redirect_target(request, next_url, reverse("users:profile", kwargs={"pk": user.pk})))
    else:
        form = CustomLoginForm()

    return render(request, "users/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_POST
def logout_view(request):
    """User logout view (POST only, so a link or prefetch can't end a session)"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("users:login")


def _export_filename(user):
    return f"djangoversehub-export-{user.username}-{timezone.now():%Y%m%d}.json"


def verify_email_view(request, token):
    """Confirm an email address from the signed link sent at signup."""
    try:
        user = load_email_verification_token(token)
    except signing.SignatureExpired:
        return render(request, "users/verify_email_failed.html", {"reason": "expired"}, status=400)
    except signing.BadSignature:
        return render(request, "users/verify_email_failed.html", {"reason": "invalid"}, status=400)

    if user.email_verified:
        messages.info(request, "Your email address was already verified.")
    else:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        logger.info("Email verified for user %s (%s)", user.pk, user.email)
        messages.success(request, "Your email address has been verified. Thank you!")

    if request.user.is_authenticated:
        return redirect("users:settings")
    return redirect("users:login")


@login_required
@require_POST
def resend_verification_view(request):
    """Send a fresh verification link, at most once per 10 minutes per user."""
    user = request.user
    fallback = reverse("users:settings")
    back = _safe_redirect_target(request, request.META.get("HTTP_REFERER"), fallback)

    if user.email_verified:
        messages.info(request, "Your email address is already verified.")
        return redirect(back)

    # cache.add is atomic: it only succeeds when no cooldown key exists yet.
    if not cache.add(resend_verification_cache_key(user), timezone.now().isoformat(), RESEND_VERIFICATION_COOLDOWN):
        messages.warning(request, "A verification email was sent recently. Please wait 10 minutes and try again.")
        return redirect(back)

    if send_verification_email(user):
        messages.success(request, f"We've sent a new verification link to {user.email}.")
    else:
        messages.error(request, "We couldn't send the verification email right now. Please try again later.")
    return redirect(back)


def password_reset_view(request):
    """Request a password-reset link. The response never reveals whether the address exists."""
    if request.user.is_authenticated:
        return redirect("users:settings")

    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            if user is not None:
                send_password_reset_email(user)
            messages.success(
                request,
                "If an account exists for that email address, we've sent a link to reset your password.",
            )
            return redirect("users:login")
    else:
        form = PasswordResetRequestForm()

    return render(request, "users/password_reset.html", {"form": form})


def password_reset_confirm_view(request, token):
    """Choose a new password from the signed link in the reset email."""
    try:
        user = load_password_reset_token(token)
    except signing.BadSignature:
        return render(request, "users/password_reset_confirm.html", {"validlink": False}, status=400)

    if request.method == "POST":
        form = SetPasswordForm(user, request.POST)
        if form.is_valid():
            form.save()
            logger.info("Password reset completed for user %s", user.pk)
            messages.success(request, "Your password has been reset. You can now sign in.")
            return redirect("users:login")
    else:
        form = SetPasswordForm(user)

    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-control")

    return render(request, "users/password_reset_confirm.html", {"form": form, "validlink": True})


@login_required
@require_POST
def export_data_view(request):
    """Download everything stored about the current user as a JSON attachment."""
    response = JsonResponse(build_user_export(request.user), encoder=DjangoJSONEncoder, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{_export_filename(request.user)}"'
    return response


@login_required
@require_http_methods(["GET", "POST"])
def delete_account_view(request):
    """Confirm (GET) and perform (POST, password required) account deletion."""
    user = request.user
    will_anonymise = has_published_content(user)

    if request.method == "POST":
        form = DeleteAccountForm(user, request.POST)
        if form.is_valid():
            outcome = delete_or_anonymise_user(user)
            logout(request)
            if outcome == "anonymised":
                messages.success(
                    request,
                    "Your account has been closed and your personal data removed. "
                    "Your published articles remain, attributed to a deleted user.",
                )
            else:
                messages.success(request, "Your account and all of its data have been deleted.")
            return redirect("users:login")
    else:
        form = DeleteAccountForm(user)

    return render(request, "users/delete_account.html", {"form": form, "will_anonymise": will_anonymise})


class UserListView(ListView):
    """List all users (public profiles)"""

    model = CustomUser
    template_name = "users/user_list.html"
    context_object_name = "users"
    paginate_by = 20

    def get_queryset(self):
        queryset = (
            CustomUser.objects.filter(is_active=True, profile__is_public=True)
            .select_related("profile")
            .order_by("-date_joined")
        )

        query = self.request.GET.get("q", "").strip()
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) | Q(profile__full_name__icontains=query) | Q(profile__bio__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        context["following_ids"] = (
            set(self.request.user.following_set.values_list("following_id", flat=True))
            if self.request.user.is_authenticated
            else set()
        )
        return context


class LeaderboardView(ListView):
    """Top users ranked by published articles and total article views"""

    template_name = "users/leaderboard.html"
    context_object_name = "leaders"
    paginate_by = 25

    def get_queryset(self):
        published = Q(articles__status="published")
        return (
            CustomUser.objects.filter(is_active=True, profile__is_public=True)
            .select_related("profile")
            .annotate(
                published_count=Count("articles", filter=published, distinct=True),
                total_views=Coalesce(Sum("articles__views_count", filter=published), Value(0)),
            )
            .filter(published_count__gt=0)
            .order_by("-published_count", "-total_views", "username")
        )


class ProfileDetailView(DetailView):
    """View user profile"""

    model = CustomUser
    template_name = "users/profile.html"
    context_object_name = "profile_user"

    def get_object(self, queryset=None):
        user = get_object_or_404(
            CustomUser.objects.select_related("profile"),
            pk=self.kwargs["pk"],
            is_active=True,
        )
        profile, _ = Profile.objects.get_or_create(user=user)

        if not profile.is_public and user != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("This profile is private.")

        return user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        viewer = self.request.user

        articles, comments, timeline = _user_activity(user, limit=10)
        published_articles = [a for a in articles if a.status == "published"]

        context.update(
            {
                "is_own_profile": viewer == user,
                "is_following": viewer.is_authenticated and viewer != user and viewer.is_following(user),
                "followers_count": user.followers_count,
                "following_count": user.following_count,
                "articles_count": _published_articles_for(user).count(),
                "comments_count": _comment_model().objects.filter(author=user, is_active=True).count(),
                "recent_articles": published_articles if viewer != user else articles,
                "recent_comments": comments,
                "recent_activities": timeline,
            }
        )
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update the current user's own profile"""

    model = Profile
    form_class = ProfileForm
    template_name = "users/profile_edit.html"

    def get_object(self, queryset=None):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile

    def get_success_url(self):
        return reverse("users:profile", kwargs={"pk": self.request.user.pk})

    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully!")
        return super().form_valid(form)


@login_required
def profile_settings_view(request):
    """User profile settings"""
    profile, _ = Profile.objects.get_or_create(user=request.user)
    user_form = UserUpdateForm(instance=request.user)
    profile_form = ProfileForm(instance=profile)
    password_form = PasswordChangeForm(request.user)

    if request.method == "POST":
        if "update_profile" in request.POST:
            user_form = UserUpdateForm(request.POST, instance=request.user)
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, "Profile updated successfully!")
                return redirect("users:settings")

        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                # Keep the current session alive after the password change.
                login(request, request.user)
                messages.success(request, "Password changed successfully!")
                return redirect("users:settings")

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
        "password_form": password_form,
    }

    return render(request, "users/settings.html", context)


@login_required
def following_view(request):
    """Who the current user follows, and who follows them"""
    following = request.user.following.filter(is_active=True).select_related("profile").order_by("username")
    followers = request.user.followers.filter(is_active=True).select_related("profile").order_by("username")
    following_ids = set(following.values_list("pk", flat=True))

    context = {
        "following": following,
        "followers": followers,
        "following_ids": following_ids,
        "following_count": len(following_ids),
        "followers_count": followers.count(),
    }
    return render(request, "users/following.html", context)


@login_required
def activity_view(request):
    """The current user's recent articles and comments"""
    articles, comments, timeline = _user_activity(request.user, limit=30)
    context = {
        "recent_articles": articles,
        "recent_comments": comments,
        "recent_activities": timeline,
    }
    return render(request, "users/activity.html", context)


def _follow_response(request, ok, message, target, http_status=200, **extra):
    """JSON for XHR callers, otherwise flash + redirect back."""
    if _wants_json(request):
        payload = {"success": ok, "message": message}
        payload.update(extra)
        return JsonResponse(payload, status=http_status)

    (messages.success if ok else messages.error)(request, message)
    fallback = reverse("users:profile", kwargs={"pk": target.pk})
    return redirect(_safe_redirect_target(request, request.META.get("HTTP_REFERER"), fallback))


def _follow_toggle(request, pk, follow):
    if not request.user.is_authenticated:
        if _wants_json(request):
            return JsonResponse({"success": False, "message": "Authentication required."}, status=401)
        fallback = reverse("users:profile", kwargs={"pk": pk})
        return redirect_to_login(
            _safe_redirect_target(request, request.META.get("HTTP_REFERER"), fallback),
            login_url=reverse("users:login"),
        )

    target = get_object_or_404(CustomUser.objects.select_related("profile"), pk=pk, is_active=True)

    if target == request.user:
        return _follow_response(request, False, "You cannot follow yourself.", target, 400)

    if follow and not target.profile.is_public:
        return _follow_response(request, False, "This profile is private.", target, 403)

    if follow:
        _, created = request.user.follow(target)
        message = f"You are now following {target.username}." if created else f"You already follow {target.username}."
    else:
        removed = request.user.unfollow(target)
        message = f"You unfollowed {target.username}." if removed else f"You were not following {target.username}."

    return _follow_response(
        request,
        True,
        message,
        target,
        is_following=follow,
        followers_count=target.followers_count,
    )


@require_POST
def follow_view(request, pk):
    return _follow_toggle(request, pk, follow=True)


@require_POST
def unfollow_view(request, pk):
    return _follow_toggle(request, pk, follow=False)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class IsSelfOrReadOnly(permissions.BasePermission):
    """Users may only modify their own user record (follow actions are open)."""

    guarded_actions = ("update", "partial_update", "destroy")

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if getattr(view, "action", None) not in self.guarded_actions:
            return True
        return obj.pk == request.user.pk


class IsProfileOwnerOrReadOnly(permissions.BasePermission):
    """Users may only modify their own profile."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.pk


class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    """API ViewSet for User operations.

    Account creation happens through `register`; deletion through `DELETE /users/me/`.
    """

    queryset = CustomUser.objects.filter(is_active=True)
    # Token first so anonymous requests get a 401 (with WWW-Authenticate) rather than 403.
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsSelfOrReadOnly]
    public_actions = ("register", "login")

    def get_serializer_class(self):
        if self.action == "list" or self.action in ("followers", "following"):
            return UserListSerializer
        if self.action in ("update", "partial_update"):
            return UserUpdateSerializer
        if self.action == "register":
            return UserRegistrationSerializer
        if self.action == "login":
            return UserLoginSerializer
        if self.action == "change_password":
            return PasswordChangeSerializer
        return UserSerializer

    def get_permissions(self):
        if self.action in self.public_actions:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()

        # Only expose public profiles, plus the requester's own record.
        if self.request.user.is_authenticated:
            queryset = queryset.filter(Q(profile__is_public=True) | Q(id=self.request.user.id))
        else:
            queryset = queryset.filter(profile__is_public=True)

        return queryset.select_related("profile")

    def _user_response(self, user, http_status=status.HTTP_200_OK):
        token, _ = Token.objects.get_or_create(user=user)
        return Response(
            {
                "user": UserSerializer(user, context=self.get_serializer_context()).data,
                "token": token.key,
            },
            status=http_status,
        )

    @action(detail=False, methods=["get", "patch", "delete"])
    def me(self, request):
        """Get, update, or delete (password required in the body) the current user's record"""
        if request.method == "DELETE":
            serializer = AccountDeletionSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            outcome = delete_or_anonymise_user(request.user)
            return Response({"detail": "Account removed.", "outcome": outcome}, status=status.HTTP_200_OK)
        if request.method == "PATCH":
            serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
        serializer = UserSerializer(request.user, context=self.get_serializer_context())
        return Response(serializer.data)

    @action(detail=False, methods=["get", "post"], url_path="me/export")
    def export(self, request):
        """Download the current user's data (GDPR export) as a JSON attachment"""
        response = Response(build_user_export(request.user))
        response["Content-Disposition"] = f'attachment; filename="{_export_filename(request.user)}"'
        return response

    @action(detail=False, methods=["post"])
    def register(self, request):
        """Register new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        transaction.on_commit(lambda: send_verification_email(user))
        return self._user_response(user, status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def login(self, request):
        """User login endpoint"""
        serializer = UserLoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        client_info = get_client_info(request)
        user.update_login_stats(client_info["ip_address"])

        return self._user_response(user)

    @action(detail=False, methods=["post"])
    def logout(self, request):
        """User logout endpoint (revokes the API token)"""
        Token.objects.filter(user=request.user).delete()
        return Response({"message": "Successfully logged out"})

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        """Change user password"""
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Password changed successfully"})

    @action(detail=True, methods=["post"])
    def follow(self, request, pk=None):
        """Follow this user"""
        target = self.get_object()
        if target == request.user:
            return Response({"detail": "You cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)
        _, created = request.user.follow(target)
        return Response(
            {"is_following": True, "created": created, "followers_count": target.followers_count},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post", "delete"])
    def unfollow(self, request, pk=None):
        """Unfollow this user"""
        target = self.get_object()
        removed = request.user.unfollow(target)
        return Response({"is_following": False, "removed": removed, "followers_count": target.followers_count})

    def _paginated_users(self, queryset):
        queryset = (
            queryset.filter(is_active=True, profile__is_public=True).select_related("profile").order_by("username")
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def followers(self, request, pk=None):
        """Users following this user"""
        return self._paginated_users(self.get_object().followers)

    @action(detail=True, methods=["get"])
    def following(self, request, pk=None):
        """Users this user follows"""
        return self._paginated_users(self.get_object().following)


class ProfileViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """API ViewSet for Profile operations (profiles are created with the user)"""

    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsProfileOwnerOrReadOnly]
    public_actions = ("list", "retrieve", "search")

    def get_queryset(self):
        queryset = super().get_queryset()

        if self.request.user.is_authenticated:
            queryset = queryset.filter(Q(is_public=True) | Q(user=self.request.user))
        else:
            queryset = queryset.filter(is_public=True)

        return queryset.filter(user__is_active=True).select_related("user")

    def get_permissions(self):
        if self.action in self.public_actions:
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_object(self):
        """`me` resolves to the requester's own profile"""
        if self.kwargs.get("pk") == "me":
            if not self.request.user.is_authenticated:
                raise NotAuthenticated()
            profile, _ = Profile.objects.get_or_create(user=self.request.user)
            return profile
        return super().get_object()

    @action(detail=False, methods=["get"])
    def search(self, request):
        """Search public profiles"""
        query = request.GET.get("q", "").strip()
        if not query:
            return Response({"results": [], "count": 0})

        profiles = Profile.objects.get_public_profiles().search_profiles(query).select_related("user")[:20]
        serializer = PublicProfileSerializer(profiles, many=True, context=self.get_serializer_context())

        return Response({"results": serializer.data, "count": len(serializer.data)})

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        """Get profile statistics (own profile or public profiles only)"""
        if pk == "me":
            profile = self.get_object()
        else:
            profile = get_object_or_404(Profile.objects.select_related("user"), pk=pk)

        if profile.user != request.user and not (profile.is_public and profile.user.is_active):
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        from .utils import UserStatsCalculator

        stats = UserStatsCalculator.get_user_activity_stats(profile.user)
        completion = UserStatsCalculator.calculate_profile_completion(profile)

        return Response({"activity_stats": stats, "profile_completion": completion})
