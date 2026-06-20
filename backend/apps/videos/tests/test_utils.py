"""Tests for video media-probing utilities (duration extraction)."""

from datetime import timedelta
from unittest.mock import Mock, patch

from apps.videos.utils import extract_video_duration


class TestExtractVideoDuration:
    """Test suite for extract_video_duration (ffprobe wrapper)."""

    @patch("apps.videos.utils.subprocess.run")
    def test_parses_ffprobe_duration_into_timedelta(self, mock_run):
        """A numeric ffprobe output is parsed into a timedelta."""
        mock_run.return_value = Mock(stdout="125.5\n")

        result = extract_video_duration("/tmp/video.mp4")

        assert result == timedelta(seconds=125.5)

    @patch(
        "apps.videos.utils.subprocess.run",
        side_effect=FileNotFoundError("ffprobe not found"),
    )
    def test_returns_none_when_ffprobe_missing(self, mock_run):
        """If ffprobe is not installed, returns None instead of raising."""
        assert extract_video_duration("/tmp/video.mp4") is None

    @patch("apps.videos.utils.subprocess.run")
    def test_returns_none_on_non_numeric_output(self, mock_run):
        """Garbage ffprobe output yields None rather than crashing."""
        mock_run.return_value = Mock(stdout="N/A\n")

        assert extract_video_duration("/tmp/video.mp4") is None

    @patch("apps.videos.utils.subprocess.run")
    def test_returns_none_on_zero_duration(self, mock_run):
        """A non-positive duration is treated as unknown (None)."""
        mock_run.return_value = Mock(stdout="0\n")

        assert extract_video_duration("/tmp/video.mp4") is None
