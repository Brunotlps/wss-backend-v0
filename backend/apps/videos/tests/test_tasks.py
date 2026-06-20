"""Tests for the videos Celery tasks (async duration extraction)."""

from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest

from apps.videos.factories import VideoFactory
from apps.videos.tasks import extract_video_duration_async


def _video_with_file():
    """Create a Video with a real (tiny) file attached."""
    return VideoFactory(
        file=SimpleUploadedFile("clip.mp4", b"\x00\x01", content_type="video/mp4")
    )


@pytest.mark.django_db
class TestExtractVideoDurationAsync:
    """Test suite for extract_video_duration_async."""

    @patch(
        "apps.videos.utils.extract_video_duration",
        return_value=timedelta(seconds=200),
    )
    def test_sets_duration_and_marks_processed(self, mock_extract):
        """On success, the task persists duration and sets is_processed."""
        video = _video_with_file()

        extract_video_duration_async(video.id)

        video.refresh_from_db()
        assert video.duration == timedelta(seconds=200)
        assert video.is_processed is True

    @patch("apps.videos.utils.extract_video_duration", return_value=None)
    def test_leaves_duration_null_when_extraction_fails(self, mock_extract):
        """If extraction returns None, duration stays NULL (re-runnable)."""
        video = _video_with_file()

        extract_video_duration_async(video.id)

        video.refresh_from_db()
        assert video.duration is None
        assert video.is_processed is False

    @patch("apps.videos.utils.extract_video_duration")
    def test_missing_video_is_a_noop(self, mock_extract):
        """A deleted/unknown video id does not raise."""
        extract_video_duration_async(999999)

        mock_extract.assert_not_called()

    @patch("apps.videos.utils.extract_video_duration")
    def test_video_without_file_is_skipped(self, mock_extract):
        """A video with no file is skipped without probing."""
        video = VideoFactory(file=None)

        extract_video_duration_async(video.id)

        mock_extract.assert_not_called()
