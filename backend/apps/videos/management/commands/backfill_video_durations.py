"""Backfill ``duration`` for existing videos that have a file but no duration.

Usage:
    python manage.py backfill_video_durations          # enqueue Celery tasks
    python manage.py backfill_video_durations --sync    # run inline (no worker)
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.videos.models import Video
from apps.videos.tasks import extract_video_duration_async


class Command(BaseCommand):
    """Enqueue (or run) duration extraction for videos missing a duration."""

    help = "Extract duration for videos that have a file but no duration yet."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run extraction inline instead of enqueuing Celery tasks.",
        )

    def handle(self, *args, **options) -> None:
        """Find target videos and dispatch extraction for each."""
        videos = Video.objects.filter(duration__isnull=True).exclude(
            Q(file="") | Q(file__isnull=True)
        )
        count = videos.count()
        self.stdout.write(f"Videos to backfill: {count}")

        for video in videos.iterator():
            if options["sync"]:
                extract_video_duration_async(video.id)
            else:
                extract_video_duration_async.delay(video.id)

        verb = "Processed" if options["sync"] else "Enqueued"
        self.stdout.write(self.style.SUCCESS(f"{verb} {count} video(s)."))
