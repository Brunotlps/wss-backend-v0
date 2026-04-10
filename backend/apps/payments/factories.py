"""Factory Boy factories for the payments app."""

import factory
from factory.django import DjangoModelFactory

from apps.courses.factories import CourseFactory
from apps.users.factories import UserFactory

from .models import Payment


class PaymentFactory(DjangoModelFactory):
    """Factory for Payment model."""

    class Meta:
        model = Payment

    user = factory.SubFactory(UserFactory)
    course = factory.SubFactory(CourseFactory)
    amount = factory.LazyAttribute(lambda obj: obj.course.price)
    currency = "brl"
    stripe_payment_intent_id = factory.Sequence(lambda n: f"pi_test_{n:08d}")
    status = Payment.Status.SUCCEEDED

    class Params:
        pending = factory.Trait(status=Payment.Status.PENDING)
        failed = factory.Trait(status=Payment.Status.FAILED)
