"""Tests for certificate data migrations."""

import importlib

from django.apps import apps as django_apps
from django.utils import timezone

import pytest

from apps.certificates.factories import CertificateFactory
from apps.enrollments.factories import EnrollmentFactory

backfill_migration = importlib.import_module(
    "apps.certificates.migrations.0005_backfill_certificate_is_valid"
)


@pytest.mark.django_db
class TestBackfillIsValid:
    """The #73 follow-up backfill re-validates legitimate certificates.

    Old code created certificates with is_valid=False and only flipped it to
    True after PDF generation, so legitimate certificates whose PDF is merely
    pending (never failed, never revoked) would be reported as "revoked".
    The backfill sets is_valid=True where is_valid=False AND
    pdf_generation_failed_at IS NULL, leaving genuinely failed ones for review.
    """

    def test_revalidates_non_revoked_pending_certificate(self):
        """is_valid=False with no failure timestamp → flipped to True."""
        cert = CertificateFactory(is_valid=False, pdf_generation_failed_at=None)

        backfill_migration.backfill_is_valid(django_apps, None)

        cert.refresh_from_db()
        assert cert.is_valid is True

    def test_leaves_failed_certificate_untouched(self):
        """is_valid=False WITH a failure timestamp → left False for review."""
        cert = CertificateFactory(
            is_valid=False,
            pdf_generation_failed_at=timezone.now(),
        )

        backfill_migration.backfill_is_valid(django_apps, None)

        cert.refresh_from_db()
        assert cert.is_valid is False

    def test_leaves_already_valid_certificate_untouched(self):
        """is_valid=True → stays True."""
        cert = CertificateFactory(is_valid=True)

        backfill_migration.backfill_is_valid(django_apps, None)

        cert.refresh_from_db()
        assert cert.is_valid is True

    def test_only_affects_intended_rows(self):
        """Mixed set: only the non-revoked pending one flips."""
        pending = CertificateFactory(
            enrollment=EnrollmentFactory(),
            is_valid=False,
            pdf_generation_failed_at=None,
        )
        failed = CertificateFactory(
            enrollment=EnrollmentFactory(),
            is_valid=False,
            pdf_generation_failed_at=timezone.now(),
        )
        valid = CertificateFactory(enrollment=EnrollmentFactory(), is_valid=True)

        backfill_migration.backfill_is_valid(django_apps, None)

        for cert in (pending, failed, valid):
            cert.refresh_from_db()
        assert pending.is_valid is True
        assert failed.is_valid is False
        assert valid.is_valid is True
