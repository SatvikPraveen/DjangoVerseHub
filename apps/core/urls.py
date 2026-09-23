# File: DjangoVerseHub/apps/core/urls.py

from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .sitemaps import sitemaps

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("search/", views.search_view, name="search"),
    # Informational pages
    path("getting-started/", views.GettingStartedView.as_view(), name="getting-started"),
    path("guidelines/", views.GuidelinesView.as_view(), name="guidelines"),
    path("faq/", views.FAQView.as_view(), name="faq"),
    path("api-docs/", views.APIDocsView.as_view(), name="api"),
    path("privacy/", views.PrivacyView.as_view(), name="privacy"),
    path("terms/", views.TermsView.as_view(), name="terms"),
    path("cookies/", views.CookiesView.as_view(), name="cookies"),
    # Forms
    path("contact/", views.contact_view, name="contact"),
    path("feedback/", views.feedback_view, name="feedback"),
    path("newsletter/subscribe/", views.newsletter_signup_view, name="newsletter_signup"),
    path("newsletter/confirm/<str:token>/", views.newsletter_confirm_view, name="newsletter_confirm"),
    path("newsletter/unsubscribe/<str:token>/", views.newsletter_unsubscribe_view, name="newsletter_unsubscribe"),
    # SEO
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots"),
]
