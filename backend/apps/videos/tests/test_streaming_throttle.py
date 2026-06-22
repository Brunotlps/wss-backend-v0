"""The protected video streaming endpoint uses a dedicated, generous throttle (#112).

A browser ``<video>`` fires many Range requests per viewing session (initial
buffering plus every seek), each hitting ``VideoFileView`` to validate the
signed token and return the X-Accel-Redirect. Under the global ``anon`` throttle
(100/hour) a single session can exhaust the limit and get 429s mid-playback —
the intermittent-playback symptom. The endpoint instead uses the ``video_stream``
scope, sized to absorb a real session while still capping pathological abuse.
"""

from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile

from rest_framework.throttling import SimpleRateThrottle

import pytest

from apps.videos.factories import VideoFactory
from apps.videos.signing import sign_video_stream


@pytest.fixture(autouse=True)
def clear_cache():
    """Reset throttle counters before and after each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestVideoStreamingThrottle:
    """GET /api/videos/{id}/file/?sig= throttling behaviour (#112)."""

    def _url(self, video):
        return f"/api/videos/{video.pk}/file/?sig={sign_video_stream(video.pk)}"

    def _video(self):
        return VideoFactory(
            file=SimpleUploadedFile("v.mp4", b"\x00\x01", content_type="video/mp4")
        )

    @patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"anon": "2/hour"})
    def test_not_subject_to_anon_throttle(self, api_client):
        """A signed <video src> is not limited by the global anon rate."""
        url = self._url(self._video())

        # anon is 2/hour here; the endpoint uses the video_stream scope instead,
        # so a player firing more than that must never be 429ed.
        statuses = [api_client.get(url).status_code for _ in range(5)]

        assert 429 not in statuses
        assert all(status == 200 for status in statuses)

    @patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"video_stream": "2/hour"})
    def test_scoped_throttle_still_caps_abuse(self, api_client):
        """The dedicated video_stream scope still enforces a ceiling."""
        url = self._url(self._video())

        # video_stream forced to 2/hour: first two pass, the third is blocked.
        assert api_client.get(url).status_code == 200
        assert api_client.get(url).status_code == 200
        assert api_client.get(url).status_code == 429
