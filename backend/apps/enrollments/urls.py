"""
Enrollment Application URL Configuration.

This module defines the URL routing configuration for the Enrollments application.
It configures RESTful API endpoints using Django REST Framework's DefaultRouter
to automatically generate CRUD routes for enrollment and lesson progress management.

Purpose:
    - Provides URL patterns for the EnrollmentViewSet (CRUD operations for enrollments)
    - Provides URL patterns for the LessonProgressViewSet (CRUD operations for lesson progress)
    - Enables RESTful API access to enrollment-related resources

Integration:
    - Registers viewsets that handle enrollment creation, retrieval, update, and deletion
    - Routes HTTP requests to appropriate view handlers
    - Integrates with the main project's URL configuration through inclusion in the root urlpatterns
    - Supports standard REST operations with automatic route generation via DefaultRouter
"""

from rest_framework.routers import DefaultRouter
from .views import EnrollmentViewSet, LessonProgressViewSet

router = DefaultRouter()

# Register viewsets
router.register(r'enrollments', EnrollmentViewSet, basename='enrollment')
router.register(r'progress', LessonProgressViewSet, basename='progress')

urlpatterns = router.urls