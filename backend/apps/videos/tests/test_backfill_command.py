"""Tests for the backfill_video_durations management command."""

from datetime import timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

import pytest

from apps.videos.factories import VideoFactory


def _file(name="clip.mp4"):
    return SimpleUploadedFile(name, b"\x00\x01", content_type="video/mp4")


@pytest.mark.django_db
class TestBackfillVideoDurations:
    """Command enqueues extraction only for videos missing a duration."""

    @patch("apps.videos.tasks.extract_video_duration_async.delay")
    def test_enqueues_only_videos_with_file_and_no_duration(self, mock_delay):
        """Videos without a file or already having a duration are skipped."""
        target = VideoFactory(file=_file("a.mp4"), duration=None)
        VideoFactory(file=None, duration=None)  # no file -> skip
        VideoFactory(file=_file("b.mp4"), duration=timedelta(seconds=5))  # done

        call_command("backfill_video_durations")

        mock_delay.assert_called_once_with(target.id)
