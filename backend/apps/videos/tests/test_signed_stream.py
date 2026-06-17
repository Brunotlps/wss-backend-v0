"""Tests for signed, short-lived video streaming URLs.

Protected video bytes are served via X-Accel-Redirect and require enrollment.
Because a browser ``<video src>`` cannot send an Authorization header, the
frontend first calls ``/api/videos/{id}/stream-url/`` (JWT + IsEnrolled) to get a
short-lived signed URL that the ``/file/`` endpoint accepts without a header.

Contract:
- ``GET /api/videos/{id}/stream-url/`` → 200 ``{"url": ".../file/?sig=..."}`` for
  authorized users; 401 anonymous, 403 non-enrolled, 404 no file.
- ``GET /api/videos/{id}/file/?sig=...`` serves bytes when the signature is valid,
  not expired, and bound to that video — otherwise falls back to enrollment gating.
"""

from unittest import mock
from urllib.parse import urlparse

from django.core.cache import cache

from rest_framework import status

import pytest

from apps.courses.factories import CourseFactory
from apps.enrollments.models import Enrollment
from apps.videos.factories import LessonFactory, VideoFactory


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear Django cache before and after each test."""
    cache.clear()
    yield
    cache.clear()


def _protected_video(name="videos/2026/06/lesson.mp4", course=None):
    """Create a non-preview video attached to a published course."""
    course = course or CourseFactory(is_published=True)
    video = VideoFactory()
    video.file = name
    video.save(update_fields=["file"])
    LessonFactory(course=course, video=video, order=2, is_free_preview=False)
    return video, course


def _path_with_query(url):
    """Return the path?query portion of an absolute URL for the test client."""
    parsed = urlparse(url)
    return f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path


@pytest.mark.django_db
class TestVideoStreamURLEndpoint:
    """``/stream-url/`` issues a signed URL only to authorized users."""

    def _url(self, video):
        return f"/api/videos/{video.pk}/stream-url/"

    def test_anonymous_denied(self, api_client):
        video, _ = _protected_video()
        response = api_client.get(self._url(video))
        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_enrolled_denied(self, auth_client):
        video, _ = _protected_video()
        response = auth_client.get(self._url(video))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_enrolled_gets_signed_url(self, auth_client):
        video, course = _protected_video()
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)

        response = auth_client.get(self._url(video))

        assert response.status_code == status.HTTP_200_OK
        url = response.data["url"]
        assert f"/api/videos/{video.pk}/file/" in url
        assert "sig=" in url

    def test_preview_signed_url_is_public(self, api_client):
        course = CourseFactory(is_published=True)
        video = VideoFactory()
        video.file = "videos/2026/06/preview.mp4"
        video.save(update_fields=["file"])
        LessonFactory(course=course, video=video, order=1, is_free_preview=True)

        response = api_client.get(self._url(video))

        assert response.status_code == status.HTTP_200_OK
        assert "url" in response.data

    def test_missing_file_returns_404(self, auth_client):
        course = CourseFactory(is_published=True)
        video = VideoFactory()  # no file
        LessonFactory(course=course, video=video, order=2, is_free_preview=False)
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)

        response = auth_client.get(self._url(video))

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestSignedFileAccess:
    """``/file/?sig=...`` serves bytes only for a valid, bound, unexpired token."""

    def _signed_url_for(self, auth_client, video, course):
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)
        resp = auth_client.get(f"/api/videos/{video.pk}/stream-url/")
        assert resp.status_code == status.HTTP_200_OK
        return _path_with_query(resp.data["url"])

    def test_valid_signature_serves_without_auth_header(self, auth_client, api_client):
        video, course = _protected_video("videos/2026/06/signed.mp4")
        signed_path = self._signed_url_for(auth_client, video, course)

        # New anonymous client (no Authorization header) — the signature alone authorizes.
        response = api_client.get(signed_path)

        assert response.status_code == status.HTTP_200_OK
        assert response["X-Accel-Redirect"] == "/protected/videos/2026/06/signed.mp4"

    def test_tampered_signature_denied(self, auth_client, api_client):
        video, course = _protected_video()
        signed_path = self._signed_url_for(auth_client, video, course)
        tampered = signed_path[:-1] + ("A" if signed_path[-1] != "A" else "B")

        response = api_client.get(tampered)

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_signature_bound_to_video(self, auth_client, api_client):
        video_a, course = _protected_video("videos/2026/06/a.mp4")
        video_b, _ = _protected_video("videos/2026/06/b.mp4")  # different course
        signed_path_a = self._signed_url_for(auth_client, video_a, course)
        sig = urlparse(signed_path_a).query  # "sig=..."

        # Reuse video A's signature on video B's file endpoint.
        response = api_client.get(f"/api/videos/{video_b.pk}/file/?{sig}")

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_expired_signature_denied(self, api_client):
        from apps.videos.signing import sign_video_stream

        video, _ = _protected_video("videos/2026/06/old.mp4")
        # Sign far in the past so the token is expired against any sane TTL.
        with mock.patch("time.time", return_value=0):
            token = sign_video_stream(video.pk)

        response = api_client.get(f"/api/videos/{video.pk}/file/?sig={token}")

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )
