"""Tests for the videos signals (enqueue duration extraction on upload)."""

from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile

import pytest

from apps.videos.factories import VideoFactory


def _file():
    return SimpleUploadedFile("clip.mp4", b"\x00\x01", content_type="video/mp4")


@pytest.mark.django_db
class TestEnqueueDurationExtraction:
    """post_save on Video enqueues async extraction when appropriate."""

    @patch("apps.videos.tasks.extract_video_duration_async.delay")
    def test_saving_video_with_file_enqueues_extraction(
        self, mock_delay, django_capture_on_commit_callbacks
    ):
        """Uploading a video (with a file, no duration) enqueues the task."""
        with django_capture_on_commit_callbacks(execute=True):
            video = VideoFactory(file=_file())

        mock_delay.assert_called_once_with(video.pk)

    @patch("apps.videos.tasks.extract_video_duration_async.delay")
    def test_saving_video_without_file_does_not_enqueue(
        self, mock_delay, django_capture_on_commit_callbacks
    ):
        """A video with no file must not enqueue extraction."""
        with django_capture_on_commit_callbacks(execute=True):
            VideoFactory(file=None)

        mock_delay.assert_not_called()

    @patch("apps.videos.tasks.extract_video_duration_async.delay")
    def test_saving_video_with_existing_duration_does_not_enqueue(
        self, mock_delay, django_capture_on_commit_callbacks
    ):
        """An already-probed video (duration set) is not re-enqueued."""
        with django_capture_on_commit_callbacks(execute=True):
            VideoFactory(file=_file(), duration=timedelta(seconds=42))

        mock_delay.assert_not_called()
