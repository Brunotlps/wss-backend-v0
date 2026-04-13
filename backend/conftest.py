"""
Global pytest fixtures for WSS Backend test suite.

Provides shared fixtures used across all apps:
- api_client: unauthenticated DRF client
- auth_client: authenticated as regular student
- instructor_client: authenticated as instructor
- staff_client: authenticated as staff/admin
"""

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient



@pytest.fixture(scope="session", autouse=True)
def disable_sentry():
    """Disable Sentry for the entire test session.

    Prevents error-simulating tests from sending real alerts to Sentry.
    The SENTRY_DSN from .env is active in development settings, so without
    this fixture every logger.error() call in tested views fires a real event.
    """
    import sentry_sdk

    sentry_sdk.init("")


@pytest.fixture
def api_client():
    """Return unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def auth_client(db):
    """Return APIClient authenticated as a regular student."""
    from apps.users.factories import UserFactory

    user = UserFactory()
    client = APIClient()
    client.force_authenticate(user=user)
    client.user = user
    return client


@pytest.fixture
def instructor_client(db):
    """Return APIClient authenticated as an instructor."""
    from apps.users.factories import InstructorFactory

    instructor = InstructorFactory()
    client = APIClient()
    client.force_authenticate(user=instructor)
    client.user = instructor
    return client


@pytest.fixture
def staff_client(db):
    """Return APIClient authenticated as staff/admin."""
    from apps.users.factories import UserFactory

    staff = UserFactory(is_staff=True)
    client = APIClient()
    client.force_authenticate(user=staff)
    client.user = staff
    return client

@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()