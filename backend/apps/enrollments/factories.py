"""Factory Boy factories for the enrollments app."""

import factory
from factory.django import DjangoModelFactory

from apps.courses.factories import CourseFactory
from apps.users.factories import UserFactory
from apps.videos.factories import LessonFactory

from .models import Enrollment, LessonProgress


class EnrollmentFactory(DjangoModelFactory):
    """Factory for Enrollment model."""

    class Meta:
        model = Enrollment

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)
    is_active = True
    completed = False

    class Params:
        completed_enrollment = factory.Trait(
            completed=True,
        )


class LessonProgressFactory(DjangoModelFactory):
    """Factory for LessonProgress model."""

    class Meta:
        model = LessonProgress

    enrollment = factory.SubFactory(EnrollmentFactory)
    lesson = factory.SubFactory(LessonFactory)
    completed = False
    watched_duration = 0

    class Params:
        completed_lesson = factory.Trait(completed=True)
