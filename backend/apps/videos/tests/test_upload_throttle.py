"""Video creation (upload) is rate-limited per user (#57).

`security.md` and `api-conventions.md` prescribe an UploadRateThrottle
(10/day) on video uploads. Without it, an instructor account can spam the
create endpoint (storage + processing cost). The throttle applies only to
the create action; reads and other writes keep the global defaults.
"""

from django.core.cache import cache

from rest_framework import status

import pytest


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset throttle counters before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestVideoUploadThrottle:
    """POST /api/videos/ throttling behaviour (#57)."""

    URL = "/api/videos/"

    def test_upload_throttled_after_10_per_day(self, instructor_client):
        """The 11th upload in a day is rejected with 429."""
        payload = {"title": "Video"}

        for _ in range(10):
            response = instructor_client.post(self.URL, payload)
            assert response.status_code == status.HTTP_201_CREATED

        response = instructor_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_upload_limit_isolated_from_other_authenticated_requests(
        self, instructor_client
    ):
        """Ordinary authenticated reads must not consume the upload allowance.

        The upload throttle uses a dedicated scope, so it must not share the
        global ``user`` bucket: many list/retrieve GETs before uploading must
        still leave all 10 uploads available.
        """
        for _ in range(15):
            instructor_client.get(self.URL)

        payload = {"title": "Video"}
        for _ in range(10):
            response = instructor_client.post(self.URL, payload)
            assert response.status_code == status.HTTP_201_CREATED

    def test_different_users_have_separate_limits(self, api_client):
        """Each instructor has an independent upload counter."""
        from apps.users.factories import InstructorFactory

        payload = {"title": "Video"}

        user1 = InstructorFactory()
        api_client.force_authenticate(user1)
        for _ in range(10):
            api_client.post(self.URL, payload)

        user2 = InstructorFactory()
        api_client.force_authenticate(user2)
        response = api_client.post(self.URL, payload)
        assert response.status_code == status.HTTP_201_CREATED
