"""Tests for video file validators."""

import pytest
from io import BytesIO
from unittest.mock import patch, MagicMock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.videos.validators import (
    MAX_VIDEO_SIZE,
    validate_video_mimetype,
    validate_video_size,
    validate_video_extension,
)


def make_file(name="test.mp4", content=b"fake content", size=None):
    """Create a SimpleUploadedFile with controllable size."""
    f = SimpleUploadedFile(name, content, content_type="video/mp4")
    if size is not None:
        f.size = size
    return f


class TestValidateVideoSize:
    """Tests for validate_video_size."""

    def test_valid_file_size_passes(self):
        """File under 2GB passes validation."""
        f = make_file(size=100 * 1024 * 1024)  # 100MB
        validate_video_size(f)  # Should not raise

    def test_file_at_max_size_passes(self):
        """File exactly at max size passes."""
        f = make_file(size=MAX_VIDEO_SIZE)
        validate_video_size(f)  # Should not raise

    def test_file_over_max_size_raises(self):
        """File exceeding 2GB raises ValidationError."""
        f = make_file(size=MAX_VIDEO_SIZE + 1)
        with pytest.raises(ValidationError) as exc_info:
            validate_video_size(f)
        assert exc_info.value.code == "file_too_large"

    def test_error_message_contains_size_info(self):
        """ValidationError message mentions file size."""
        f = make_file(size=MAX_VIDEO_SIZE + 1024 * 1024)
        with pytest.raises(ValidationError) as exc_info:
            validate_video_size(f)
        message = str(exc_info.value.message)
        assert "MB" in message


class TestValidateVideoMimetype:
    """Tests for validate_video_mimetype."""

    @patch("apps.videos.validators.magic.from_buffer")
    def test_valid_mp4_mimetype_passes(self, mock_magic):
        """MP4 MIME type passes validation."""
        mock_magic.return_value = "video/mp4"
        f = make_file("test.mp4", b"fake mp4 header")
        validate_video_mimetype(f)  # Should not raise

    @patch("apps.videos.validators.magic.from_buffer")
    def test_valid_webm_mimetype_passes(self, mock_magic):
        """WebM MIME type passes validation."""
        mock_magic.return_value = "video/webm"
        f = make_file("test.webm", b"fake webm header")
        validate_video_mimetype(f)  # Should not raise

    @patch("apps.videos.validators.magic.from_buffer")
    def test_invalid_mimetype_raises(self, mock_magic):
        """Non-video MIME type raises ValidationError."""
        mock_magic.return_value = "text/plain"
        f = make_file("fake_video.mp4", b"this is not a video")
        with pytest.raises(ValidationError) as exc_info:
            validate_video_mimetype(f)
        assert exc_info.value.code == "invalid_mimetype"

    @patch("apps.videos.validators.magic.from_buffer")
    def test_executable_mimetype_raises(self, mock_magic):
        """Executable disguised as video raises ValidationError."""
        mock_magic.return_value = "application/x-executable"
        f = make_file("malware.mp4", b"MZ executable header")
        with pytest.raises(ValidationError) as exc_info:
            validate_video_mimetype(f)
        assert exc_info.value.code == "invalid_mimetype"

    @patch("apps.videos.validators.magic.from_buffer")
    def test_mime_detection_failure_raises(self, mock_magic):
        """If python-magic fails, raises ValidationError."""
        mock_magic.side_effect = Exception("libmagic error")
        f = make_file()
        with pytest.raises(ValidationError) as exc_info:
            validate_video_mimetype(f)
        assert exc_info.value.code == "mime_detection_failed"

    @patch("apps.videos.validators.magic.from_buffer")
    def test_file_pointer_reset_after_validation(self, mock_magic):
        """File seek position is reset to 0 after MIME check."""
        mock_magic.return_value = "video/mp4"
        f = SimpleUploadedFile("test.mp4", b"fake content", content_type="video/mp4")
        validate_video_mimetype(f)
        assert f.tell() == 0


class TestValidateVideoExtension:
    """Tests for validate_video_extension."""

    def test_mp4_extension_passes(self):
        """MP4 extension passes."""
        f = SimpleUploadedFile("video.mp4", b"", content_type="video/mp4")
        validate_video_extension(f)  # Should not raise

    def test_webm_extension_passes(self):
        """WebM extension passes."""
        f = SimpleUploadedFile("video.webm", b"", content_type="video/webm")
        validate_video_extension(f)  # Should not raise

    def test_mov_extension_passes(self):
        """MOV extension passes."""
        f = SimpleUploadedFile("video.mov", b"", content_type="video/quicktime")
        validate_video_extension(f)  # Should not raise

    def test_avi_extension_raises(self):
        """AVI extension is not allowed."""
        f = SimpleUploadedFile("video.avi", b"", content_type="video/avi")
        with pytest.raises(ValidationError) as exc_info:
            validate_video_extension(f)
        assert exc_info.value.code == "invalid_extension"

    def test_exe_extension_raises(self):
        """EXE extension is rejected."""
        f = SimpleUploadedFile(
            "malware.exe", b"", content_type="application/x-executable"
        )
        with pytest.raises(ValidationError) as exc_info:
            validate_video_extension(f)
        assert exc_info.value.code == "invalid_extension"
