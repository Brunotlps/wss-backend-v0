from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.response import FileResponse
from django.shortcuts import get_object_or_404
from .models import Certificate
from .serializers import CertificateSerializer
from .permissions import IsCertificateOwner

class CertificateViewSet(viewsets.ReadOnlyModelViewSet):
    
    """
    ViewSet for certificate management.
    
    Provides:
    - list: GET /api/certificates/
    - retrieve: GET /api/certificates/{id}/
    - download: GET /api/certificates/{id}/download/ (custom action)
    - validate_ownership: POST /api/certificates/{id}/validate/ (custom action)
    - validate_by_code: GET /api/certificates/validate/{code}/ (custom action)
    """
    
    serializer_class = CertificateSerializer
    permission_classes = [permissions.IsAuthenticated, IsCertificateOwner]
    
    def get_queryset(self):

        user = self.request.user
        return Certificate.objects.filter(
            enrollment__user=user
        ).select_related('enrollment__user', 'enrollment__course', 'enrollment__course__instructor')
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):

        certificate = self.get_object()
                
        if not certificate.pdf_file:
            return Response(
                {'error': 'PDF file not available for this certificate'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            return FileResponse(
                certificate.pdf_file.open('rb'),
                as_attachment=True,
                filename=f'certificate_{certificate.certificate_code}.pdf',
                content_type='application/pdf'
            )
        except FileNotFoundError:
            return Response(
                {'error': 'Certificate file not found on storage'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    
    @action(detail=True, methods=['post'])
    def validate_ownership(self, request, pk=None):
        
        certificate = self.get_object()
                
        return Response(
            {
                'valid': True,
                'message': 'Certificate belongs to you',
                'certificate_code': certificate.certificate_code
            },
            status=status.HTTP_200_OK
        )

    @action(
    detail=False, 
    methods=['get'],
    permission_classes=[permissions.AllowAny],
    url_path='validate/(?P<code>[^/.]+)'  
    )
    def validate_by_code(self, request, code=None):

        certificate = get_object_or_404(Certificate, certificate_code=code)

        return Response(
            {
                'valid': certificate.is_valid,
                'message': 'Certificate is valid' if certificate.is_valid else 'Certificate has been revoked',
                'certificate_code': certificate.certificate_code,
                'student_name': certificate.enrollment.user.get_full_name()
            },
            status=status.HTTP_200_OK
        )

