"""Tests for IsCertificateOwner permission."""

from rest_framework import status

import pytest

from apps.certificates.factories import CertificateFactory
from apps.enrollments.factories import EnrollmentFactory


@pytest.mark.django_db
class TestIsCertificateOwner:
    """Tests for IsCertificateOwner via CertificateViewSet."""

    URL = "/api/certificates/"

    def test_owner_can_retrieve_certificate(self, auth_client):
        """Certificate owner can access their certificate."""
        enrollment = EnrollmentFactory(user=auth_client.user)
        cert = CertificateFactory(enrollment=enrollment)
        response = auth_client.get(f"{self.URL}{cert.pk}/")
        assert response.status_code == status.HTTP_200_OK

    def test_non_owner_cannot_retrieve_certificate(self, auth_client):
        """Non-owner gets 404 (filtered queryset hides the certificate)."""
        other_cert = CertificateFactory()
        response = auth_client.get(f"{self.URL}{other_cert.pk}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_staff_can_validate_their_own_certificate(self, staff_client):
        """Staff validating their own certificate works (unaffected by #220)."""
        enrollment = EnrollmentFactory(user=staff_client.user)
        cert = CertificateFactory(enrollment=enrollment)
        response = staff_client.post(f"{self.URL}{cert.pk}/validate/")
        assert response.status_code == status.HTTP_200_OK

    def test_staff_cannot_validate_other_users_certificate(self, staff_client):
        """Staff do NOT get cross-user access on validate_ownership either
        (#220): ``get_queryset`` filters by owner for every request, so a
        certificate staff don't own 404s before any permission check runs.
        """
        other_cert = CertificateFactory()
        response = staff_client.post(f"{self.URL}{other_cert.pk}/validate/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_cannot_access_certificates(self, api_client):
        """Unauthenticated users cannot list or retrieve certificates."""
        CertificateFactory()
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
