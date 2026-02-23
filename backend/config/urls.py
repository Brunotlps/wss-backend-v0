"""
URL Configuration for the WSS Backend Project

This file defines the main URL routing for the Django project, including:
- Admin interface access
- API documentation endpoints (Swagger/ReDoc)
- API endpoint routing for different apps (users, courses, videos, enrollments)
- Static and media file serving during development

All API endpoints follow the /api/ prefix convention.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
  SpectacularAPIView,
  SpectacularSwaggerView,
  SpectacularRedocView,
)

from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def health_check(request):
    """Health check endpoint to verify API is running"""
    return Response({
        'status': 'ok',
        'message': 'WSS Backend API is running!',
        'version': '1.0.0'
    })

urlpatterns = [
   
    # Health Check
    path('api/health/', health_check, name='health-check'),
    # Django Admin
    path('admin/', admin.site.urls),

    # API Documentation (Swagger/OpenAPI)
    # API Documentation with drf-spectacular
    # OpenAPI 3.0 schema endpoint - generates the API schema in JSON/YAML format
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI - interactive API documentation interface
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # ReDoc - alternative API documentation interface with a different layout
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),  
    
    # Apps URLs
    path('api/', include('apps.users.urls')),
    path('api/', include('apps.courses.urls')),
    # path('api/videos/', include('apps.videos.urls')),
    # path('api/enrollments/', include('apps.enrollments.urls')),
]

# Django Debug Toolbar (apenas em desenvolvimento)
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

# Serve media and static files during development
# In production, these should be served by a web server like Nginx or Apache
if settings.DEBUG:
  # Serve media files (user-uploaded content like images, videos, etc.)
  urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
  # Serve static files (CSS, JavaScript, images from the project)
  urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
