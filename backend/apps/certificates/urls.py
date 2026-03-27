"""
Certificate Application URL Configuration.

This module defines the URL routing configuration for the Certificate application.
It configures RESTful API endpoints using Django REST Framework's DefaultRouter
to automatically generate routes for certificate management operations.

Purpose:
    - Provides read-only endpoints for certificate access (list, retrieve)
    - Provides custom actions for PDF download and certificate validation
    - Enables RESTful API access to certificate-related resources
    - Supports public validation endpoints for third-party verification

Routes Generated:
    Automatic (ReadOnlyModelViewSet):
    - GET /api/certificates/              → list certificates (user's own)
    - GET /api/certificates/{id}/         → retrieve certificate detail
    
    Custom Actions (@action decorators):
    - GET /api/certificates/{id}/download/           → download PDF file
    - POST /api/certificates/{id}/validate/          → validate ownership
    - GET /api/certificates/validate/{code}/         → public validation by code

Integration:
    - Registers CertificateViewSet for certificate management
    - Routes HTTP requests to appropriate view handlers
    - Integrates with main project URL configuration via inclusion
    - Supports standard REST operations with automatic route generation
    
Notes:
    - Certificates are read-only through API (created via signals)
    - Public validation endpoint requires no authentication
    - Other endpoints require IsAuthenticated + IsCertificateOwner permissions
"""

from rest_framework.routers import DefaultRouter
from .views import CertificateViewSet

router = DefaultRouter()
router.register(r'certificates', CertificateViewSet, basename='certificate')

urlpatterns = router.urls