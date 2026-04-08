"""Factory Boy factories for the videos app."""

import factory
from factory.django import DjangoModelFactory

from apps.courses.factories import CourseFactory

from .models import Lesson, Video


class VideoFactory(DjangoModelFactory):
    """Factory for Video model."""

    class Meta:
        model = Video

    title = factory.Sequence(lambda n: f"Video {n}")
    file = None  # blank=True, null=True — no real file needed
    file_size = 1024 * 1024  # 1 MB
    is_processed = False

    class Params:
        processed = factory.Trait(is_processed=True)


class LessonFactory(DjangoModelFactory):
    """Factory for Lesson model."""

    class Meta:
        model = Lesson

    title = factory.Sequence(lambda n: f"Lesson {n}")
    course = factory.SubFactory(CourseFactory)
    video = factory.SubFactory(VideoFactory)
    order = factory.Sequence(lambda n: n + 1)
    description = factory.Faker("paragraph", nb_sentences=2)
    is_free_preview = False
    duration = 10

    class Params:
        free_preview = factory.Trait(is_free_preview=True, order=1)
