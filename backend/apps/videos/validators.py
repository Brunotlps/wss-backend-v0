"""
Custom validators for video file uploads.

Validates:
- File size (max 2GB for HD 1080p videos ~1h duration)
- File extension (.mp4, .webm, .mov - browser-compatible formats)
- MIME type (prevents malware disguised as videos)

Security:
- Extension whitelist prevents executable uploads (.exe, .sh, .bat)
- Size limit prevents DoS attacks and storage exhaustion
- MIME validation detects file type spoofing (malware.exe renamed to video.mp4)

Usage:
    Add to model field:
    file = models.FileField(
        validators=[validate_video_size, validate_video_extension]
    )
"""

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import FileExtensionValidator
from django.utils.translation import gettext_lazy as _

import magic

MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB in bytes

ALLOWED_VIDEO_EXTENSIONS = ["mp4", "webm", "mov"]

ALLOWED_VIDEO_MIMETYPES = [
    "video/mp4",  # MP4 container (H.264, H.265)
    "video/webm",  # WebM container (VP8, VP9)
    "video/quicktime",  # MOV container (QuickTime)
    "video/x-m4v",  # M4V (Apple variant of MP4)
]


def validate_video_size(file: File) -> None:
    """
    Validate video file size does not exceed maximum limit.

    Args:
        file: UploadedFile object from Django form/serializer

    Raises:
        ValidationError: If file size exceeds MAX_VIDEO_SIZE (2GB)
    """
    file_size = file.size
    max_size_mb = MAX_VIDEO_SIZE / (1024 * 1024)  # Convert to MB for error message

    if file_size > MAX_VIDEO_SIZE:
        current_size_mb = file_size / (1024 * 1024)
        raise ValidationError(
            _(
                "Very large file: %(current_size)sMB. "
                "Maximum size allowed: %(max_size)sMB (2GB)."
            ),
            code="file_too_large",
            params={
                "current_size": f"{current_size_mb:.1f}",
                "max_size": f"{max_size_mb:.0f}",
            },
        )


def validate_video_mimetype(file: File) -> None:
    """
    Validate file is actually a video by inspecting MIME type.

    Uses python-magic (libmagic) to read file's magic numbers (first bytes)
    and detect real file type, preventing extension spoofing attacks.

    Args:
        file: UploadedFile object from Django form/serializer

    Raises:
        ValidationError: If MIME type is not in ALLOWED_VIDEO_MIMETYPES

    Security:
        Prevents attacks like:
        1. Attacker renames malware.exe to video.mp4
        2. Extension validator passes (sees .mp4)
        3. MIME validator reads first bytes: detects "application/x-executable"
        4. Upload rejected
    """
    file_head = file.read(2048)
    file.seek(0)

    # Detect MIME type from content (not extension)
    try:
        mime_type = magic.from_buffer(file_head, mime=True)
    except Exception:
        raise ValidationError(
            _("Unable to determine file type. Make sure you upload a valid video."),
            code="mime_detection_failed",
        )

    if mime_type not in ALLOWED_VIDEO_MIMETYPES:
        raise ValidationError(
            _("Invalid file type: %(mime_type)s. Allowed types: %(allowed_types)s."),
            code="invalid_mimetype",
            params={
                "mime_type": mime_type,
                "allowed_types": ", ".join(ALLOWED_VIDEO_MIMETYPES),
            },
        )


# Django's built-in extension validator
# Checks file extension against whitelist (case-insensitive)
validate_video_extension = FileExtensionValidator(
    allowed_extensions=ALLOWED_VIDEO_EXTENSIONS,
    message=_("Invalid file extension. Allowed extensions: %(allowed_extensions)s."),
    code="invalid_extension",
)
