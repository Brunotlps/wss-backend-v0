"""Factory Boy factories for the certificates app."""

import factory
from factory.django import DjangoModelFactory

from apps.enrollments.factories import EnrollmentFactory

from .models import Certificate
from .utils import generate_certificate_code


class CertificateFactory(DjangoModelFactory):
    """Factory for Certificate model."""

    class Meta:
        model = Certificate

    enrollment = factory.SubFactory(EnrollmentFactory)
    certificate_code = factory.LazyFunction(generate_certificate_code)
    is_valid = True
