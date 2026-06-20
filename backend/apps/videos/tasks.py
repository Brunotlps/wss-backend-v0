"""Celery tasks for the videos app.

Duration extraction runs asynchronously so large uploads (up to 2GB) never
block the request/response cycle. Requires a running Celery worker (#110).
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def extract_video_duration_async(video_id: int) -> None:
    """Extract and persist a video's duration via ffprobe.

    Idempotent and self-healing: if extraction fails, ``duration`` is left
    NULL so the video is picked up again by a later save or the
    ``backfill_video_durations`` command.

    Args:
        video_id: Primary key of the Video to probe.
    """
    from apps.videos.models import Video
    from apps.videos.utils import extract_video_duration

    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.error("Video %d not found — skipping duration extraction.", video_id)
        return

    if not video.file:
        logger.warning("Video %d has no file — skipping duration extraction.", video_id)
        return

    duration = extract_video_duration(video.file.path)
    if duration is None:
        logger.error(
            "Could not extract duration for video %d — leaving it unset.", video_id
        )
        return

    video.duration = duration
    video.is_processed = True
    video.save(update_fields=["duration", "is_processed"])
    logger.info("Video %d duration set to %s.", video_id, duration)
