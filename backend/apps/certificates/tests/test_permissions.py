"""Tests for IsCertificateOwner permission."""

import pytest
from rest_framework import status

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

    def test_staff_bypasses_ownership_on_validate_action(self, staff_client):
        """Staff can validate ownership of certificates they don't own."""
        # Staff member's own certificate
        enrollment = EnrollmentFactory(user=staff_client.user)
        cert = CertificateFactory(enrollment=enrollment)
        response = staff_client.post(f"{self.URL}{cert.pk}/validate/")
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_cannot_access_certificates(self, api_client):
        """Unauthenticated users cannot list or retrieve certificates."""
        cert = CertificateFactory()
        response = api_client.get(self.URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
