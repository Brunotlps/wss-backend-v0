"""Media-probing utilities for the videos app.

Currently provides duration extraction via ``ffprobe`` (bundled with the
``ffmpeg`` system package). Kept dependency-light: a thin ``subprocess``
wrapper that never raises, returning ``None`` when the duration cannot be
determined so callers can decide how to handle missing metadata.
"""

import logging
import subprocess
from datetime import timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Hard cap so a malformed/huge file can never hang a worker indefinitely.
FFPROBE_TIMEOUT_SECONDS = 60


def extract_video_duration(file_path: str) -> Optional[timedelta]:
    """Return a video file's duration using ffprobe.

    Args:
        file_path: Absolute path to the video file on disk.

    Returns:
        The duration as a ``timedelta``, or ``None`` if it could not be
        determined (ffprobe missing, unreadable file, timeout, or no
        positive duration in the container metadata).
    """
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.error("ffprobe failed for %s: %s", file_path, exc)
        return None

    output = result.stdout.strip()
    try:
        seconds = float(output)
    except ValueError:
        logger.error(
            "ffprobe returned non-numeric duration %r for %s", output, file_path
        )
        return None

    if seconds <= 0:
        return None

    return timedelta(seconds=seconds)
