"""
Course URL Configuration

This module defines URL routing for the course management API endpoints. It uses Django REST
Framework's DefaultRouter to automatically generate RESTful URL patterns for course and category
viewsets, providing a standardized interface for course discovery, creation, and management.

Module Overview:
    This module registers two main viewsets with the router:
    
    1. CategoryViewSet: Provides read-only endpoints for course categories
       - GET /api/categories/         - List all active categories
       - GET /api/categories/{id}/    - Retrieve specific category details
    
    2. CourseViewSet: Provides full CRUD endpoints for course management
       - GET /api/courses/             - List courses (role-filtered)
       - POST /api/courses/            - Create course (instructors only)
       - GET /api/courses/{id}/        - Retrieve course details
       - PATCH /api/courses/{id}/      - Update course (owner only)
       - DELETE /api/courses/{id}/     - Delete course (owner only)
       - GET /api/courses/{id}/lessons/ - List course lessons (custom action)

Key Features:
    - Automatic URL pattern generation via DefaultRouter
    - RESTful API structure following Django REST Framework conventions
    - Support for nested resources through custom actions
    - Basename configuration for reverse URL lookups
    - Integration with project-level URL configuration

Integration Points:
    - Included in config/urls.py via path('api/', include('apps.courses.urls'))
    - Works with CategoryViewSet and CourseViewSet from views module
    - Supports URL reversal using basename (e.g., reverse('category-list'))
    - Enables API browsability through DRF's web interface

URL Patterns Generated:
    Categories (basename='category'):
    - category-list: /api/categories/
    - category-detail: /api/categories/{pk}/
    
    Courses (basename='course'):
    - course-list: /api/courses/
    - course-detail: /api/courses/{pk}/
    - course-create: POST /api/courses/
    - course-update: PATCH /api/courses/{pk}/
    - course-delete: DELETE /api/courses/{pk}/
    - course-lessons: /api/courses/{pk}/lessons/ (custom action)

Usage Example:
    # In views or serializers
    from django.urls import reverse
    
    category_url = reverse('category-list')
    # Returns: '/api/categories/'
    
    course_detail = reverse('course-detail', kwargs={'pk': 1})
    # Returns: '/api/courses/1/'
    
    lessons_url = reverse('course-lessons', kwargs={'pk': 1})
    # Returns: '/api/courses/1/lessons/'
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, CourseViewSet

# Initialize the DefaultRouter for automatic URL routing
router = DefaultRouter()

# Register CategoryViewSet with 'categories' prefix
# Generates URLs: /categories/, /categories/{id}/
router.register(r'categories', CategoryViewSet, basename='category')

# Register CourseViewSet with 'courses' prefix
# Generates URLs: /courses/, /courses/{id}/, /courses/{id}/lessons/, etc.
router.register(r'courses', CourseViewSet, basename='course')

# Export URL patterns for inclusion in project-level urls.py
urlpatterns = [
    path('', include(router.urls)),
]