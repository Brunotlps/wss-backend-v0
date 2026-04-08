"""Factory Boy factories for the courses app."""

import factory
from factory.django import DjangoModelFactory

from apps.users.factories import InstructorFactory

from .models import Category, Course


class CategoryFactory(DjangoModelFactory):
    """Factory for Course Category."""

    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")
    description = factory.Faker("paragraph", nb_sentences=1)
    is_active = True


class CourseFactory(DjangoModelFactory):
    """Factory for Course."""

    class Meta:
        model = Course

    title = factory.Sequence(lambda n: f"Course Title {n}")
    slug = factory.Sequence(lambda n: f"course-title-{n}")
    description = factory.Faker("paragraph")
    instructor = factory.SubFactory(InstructorFactory)
    category = factory.SubFactory(CategoryFactory)
    price = factory.Faker(
        "pydecimal", left_digits=3, right_digits=2, positive=True, min_value=1
    )
    difficulty = Course.DifficultyLevel.INTERMEDIATE
    is_published = True

    class Params:
        free = factory.Trait(price=0)
        unpublished = factory.Trait(is_published=False)
