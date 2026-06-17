"""Deny-tests for protected video delivery and enrollment gating.

Covers audit findings:
- #54: video bytes must be served only through an authenticated, enrollment-aware
  endpoint (X-Accel-Redirect), never as a public ``/media/`` URL in serializers.
- #55: ``VideoViewSet`` must not expose the raw ``file`` URL publicly.
- #56: preview access must derive from ``is_free_preview``, not the ``order == 1``
  heuristic.
"""

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


def _video_with_file(name="videos/2026/06/sample.mp4"):
    """Create a Video whose FileField points at a (fake) stored object.

    Direct ORM assignment bypasses upload validators, which is what we want for
    permission/serializer tests that never touch real bytes.
    """
    video = VideoFactory()
    video.file = name
    video.save(update_fields=["file"])
    return video


@pytest.mark.django_db
class TestVideoFileEndpoint:
    """The gated file endpoint must enforce enrollment before serving bytes (#54)."""

    def _url(self, video):
        return f"/api/videos/{video.pk}/file/"

    def test_anonymous_cannot_download_non_preview_file(self, api_client):
        """Anonymous GET of a non-preview video file → 403 (not the bytes)."""
        course = CourseFactory(is_published=True)
        video = _video_with_file()
        LessonFactory(course=course, video=video, order=2, is_free_preview=False)

        response = api_client.get(self._url(video))

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    def test_non_enrolled_user_cannot_download_file(self, auth_client):
        """Authenticated but non-enrolled user → 403."""
        course = CourseFactory(is_published=True)
        video = _video_with_file()
        LessonFactory(course=course, video=video, order=2, is_free_preview=False)

        response = auth_client.get(self._url(video))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_enrolled_user_gets_x_accel_redirect(self, auth_client):
        """Enrolled user → 200 and bytes delegated to Nginx via X-Accel-Redirect."""
        course = CourseFactory(is_published=True)
        video = _video_with_file("videos/2026/06/lesson2.mp4")
        LessonFactory(course=course, video=video, order=2, is_free_preview=False)
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)

        response = auth_client.get(self._url(video))

        assert response.status_code == status.HTTP_200_OK
        assert response["X-Accel-Redirect"] == "/protected/videos/2026/06/lesson2.mp4"

    def test_free_preview_file_is_public(self, api_client):
        """Free-preview lesson video stays accessible without enrollment (#56)."""
        course = CourseFactory(is_published=True)
        video = _video_with_file()
        LessonFactory(course=course, video=video, order=1, is_free_preview=True)

        response = api_client.get(self._url(video))

        assert response.status_code == status.HTTP_200_OK
        assert "X-Accel-Redirect" in response

    def test_course_instructor_can_download_own_file(self, instructor_client):
        """Course instructor bypasses enrollment for their own content."""
        course = CourseFactory(instructor=instructor_client.user, is_published=True)
        video = _video_with_file()
        LessonFactory(course=course, video=video, order=2, is_free_preview=False)

        response = instructor_client.get(self._url(video))

        assert response.status_code == status.HTTP_200_OK

    def test_missing_file_returns_404(self, auth_client):
        """Enrolled user requesting a video with no stored file → 404."""
        course = CourseFactory(is_published=True)
        video = VideoFactory()  # file is None
        LessonFactory(course=course, video=video, order=2, is_free_preview=False)
        Enrollment.objects.create(user=auth_client.user, course=course, is_active=True)

        response = auth_client.get(self._url(video))

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestSerializerDoesNotLeakFileURL:
    """Serializers must not expose a directly-fetchable media URL (#54/#55)."""

    def test_list_does_not_expose_raw_file_url(self, api_client):
        """List items expose a gated ``stream_url``, never the raw ``file``."""
        video = _video_with_file()
        LessonFactory(video=video, order=2, is_free_preview=False)

        response = api_client.get("/api/videos/")

        assert response.status_code == status.HTTP_200_OK
        item = (
            response.data["results"][0]
            if "results" in response.data
            else response.data[0]
        )
        assert "file" not in item
        assert "stream_url" in item

    def test_retrieve_does_not_expose_raw_file_url(self, instructor_client):
        """Detail view never returns the raw ``file`` media URL."""
        video = _video_with_file()
        LessonFactory(
            course=CourseFactory(instructor=instructor_client.user),
            video=video,
            order=2,
            is_free_preview=False,
        )

        response = instructor_client.get(f"/api/videos/{video.pk}/")

        assert response.status_code == status.HTTP_200_OK
        assert "file" not in response.data
