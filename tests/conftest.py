# File: DjangoVerseHub/tests/conftest.py
"""
pytest-django configuration for DjangoVerseHub.

All tests in the project automatically pick up this conftest, so no
per-test-file DJANGO_SETTINGS_MODULE override is needed.
"""

import django
import pytest
from django.conf import settings


# ---------------------------------------------------------------------------
# Tell pytest-django which settings module to use
# ---------------------------------------------------------------------------
def pytest_configure(config):
    """Called before pytest collects tests — configure Django settings."""
    import os
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'django_verse_hub.settings.test',
    )
    django.setup()


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    """DRF APIClient instance ready for use."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def user(db):
    """A regular active user created with the custom user manager."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        email='fixture@example.com',
        password='testpass123',
        username='fixtureuser',
    )


@pytest.fixture
def staff_user(db):
    """A staff user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        email='staff@example.com',
        password='testpass123',
        username='staffuser',
        is_staff=True,
    )


@pytest.fixture
def authenticated_client(client, user):
    """Django test client pre-authenticated as `user`."""
    client.force_login(user)
    return client


@pytest.fixture
def authenticated_api_client(api_client, user):
    """DRF APIClient pre-authenticated as `user`."""
    api_client.force_authenticate(user=user)
    return api_client
