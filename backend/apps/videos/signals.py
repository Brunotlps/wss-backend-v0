"""Signals for the videos app.

Enqueues asynchronous duration extraction whenever a Video that has a file
but no duration yet is saved. Covers uploads via both the DRF API and the
Django admin. The enqueue is deferred to ``transaction.on_commit`` so the
worker (a separate process) only runs once the row is committed.

Signal flow:
    Video saved (file present, duration is NULL)
      -> enqueue_duration_extraction
        -> on commit -> extract_video_duration_async.delay(video.pk)
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.videos.models import Video

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Video)
def enqueue_duration_extraction(sender, instance, **kwargs) -> None:
    """Queue duration extraction for a freshly uploaded video.

    Only enqueues when the video has a file and no duration yet, making it
    idempotent: already-processed videos and metadata-only saves are skipped.

    Note: the ``duration is not None`` guard is also what stops the task's own
    ``save(update_fields=["duration", ...])`` from re-enqueuing itself — keep it
    if this handler is refactored.

    Args:
        sender: The Video model class.
        instance: The saved Video instance.
        **kwargs: Extra signal arguments.
    """
    if not instance.file or instance.duration is not None:
        return

    from apps.videos.tasks import extract_video_duration_async

    transaction.on_commit(lambda: extract_video_duration_async.delay(instance.pk))
    logger.debug("Queued duration extraction for video %d.", instance.pk)
