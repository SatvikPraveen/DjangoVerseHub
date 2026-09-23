# File: DjangoVerseHub/apps/users/urls.py

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "users"

# API router
router = DefaultRouter()
router.register(r"users", views.UserViewSet, basename="user")
router.register(r"profiles", views.ProfileViewSet, basename="profile")

urlpatterns = [
    # Authentication
    path("signup/", views.signup_view, name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    # Email verification
    path("verify-email/resend/", views.resend_verification_view, name="resend_verification"),
    path("verify-email/<str:token>/", views.verify_email_view, name="verify_email"),
    # Password reset
    path("password-reset/", views.password_reset_view, name="password_reset"),
    path("password-reset/confirm/<str:token>/", views.password_reset_confirm_view, name="password_reset_confirm"),
    # Account data & deletion
    path("export/", views.export_data_view, name="export_data"),
    path("delete/", views.delete_account_view, name="delete_account"),
    # Profile management
    path("", views.UserListView.as_view(), name="list"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("following/", views.following_view, name="following"),
    path("activity/", views.activity_view, name="activity"),
    path("profile/<uuid:pk>/", views.ProfileDetailView.as_view(), name="profile"),
    path("profile/<uuid:pk>/follow/", views.follow_view, name="follow"),
    path("profile/<uuid:pk>/unfollow/", views.unfollow_view, name="unfollow"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile_edit"),
    path("settings/", views.profile_settings_view, name="settings"),
    # API endpoints
    path("api/", include(router.urls)),
]
