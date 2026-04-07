"""
Enrollment and Lesson Progress Filtering Module.

This module provides filter classes for querying and filtering enrollments and lesson progress data
in the WSS (Web Streaming School) backend system. It leverages django-filter to enable flexible,
API-friendly filtering capabilities for both Enrollment and LessonProgress models.

Purpose:
    - Define reusable filter classes for REST API endpoints and queryset filtering
    - Enable advanced querying of enrollment data (status, ratings, completion, certificates)
    - Enable filtering of lesson progress tracking (watch duration, completion status, dates)
    - Support filtering by course, enrollment status, ratings, review presence, and temporal fields

Integration:
    - Used by DRF (Django Rest Framework) ViewSets for automatic filtering of enrollment and
      lesson progress endpoints
    - Coordinates with the enrollments app models (Enrollment, LessonProgress) for field mapping
    - Provides standardized help text and filter definitions for API documentation
    - Supports complex queries with range filters (min/max) and date-based filtering

Classes:
    - EnrollmentFilter: Filters enrollments by course, status, ratings, certificates, and dates
    - LessonProgressFilter: Filters lesson progress by enrollment, lesson, completion status, and dates
"""

from django.db import models

import django_filters

from .models import Enrollment, LessonProgress


class EnrollmentFilter(django_filters.FilterSet):
    """
    Filter class for querying and filtering Enrollment records in the WSS backend system.

    Purpose:
        Provides a flexible, API-friendly filtering interface for Enrollment model queryset operations.
        Enables REST API endpoints to support advanced filtering capabilities across multiple enrollment
        attributes without requiring manual query construction.

    Functionality:
        - Filters enrollments by course (ID or slug)
        - Filters by enrollment status (active/inactive)
        - Filters by course completion status and certificate issuance
        - Supports rating-based filtering (exact, minimum, maximum values)
        - Filters by presence of ratings or reviews
        - Supports temporal filtering (enrollment and completion dates with range queries)

    Integration:
        - Automatically integrated with DRF ViewSets via FilterBackend configuration
        - Works seamlessly with Enrollment model fields and relationships (course, created_at, completed_at)
        - Provides standardized filter definitions and help text for API documentation and schema generation
        - Enables query parameter-based filtering in REST API endpoints without additional view logic

    Attributes:
        course: Filter by Course ID
        course__slug: Filter by course slug
        is_active: Filter by enrollment status (active/inactive)
        completed: Filter by course completion status
        certificate_issued: Filter by certificate issued status
        rating: Filter by exact rating (1-5)
        rating_min: Filter by minimum rating (gte)
        rating_max: Filter by maximum rating (lte)
        has_rating: Filter by presence of rating (custom method)
        enrolled_after: Filter by enrollment date (on or after)
        enrolled_before: Filter by enrollment date (on or before)
        completed_after: Filter by completion date (on or after)
        completed_before: Filter by completion date (on or before)
        has_review: Filter by presence of review (custom method)
    """

    course = django_filters.NumberFilter(
        field_name="course", help_text="Filter by Course ID"
    )
    course__slug = django_filters.CharFilter(
        field_name="course__slug",
        lookup_expr="exact",
        help_text="Filter by course slug",
    )
    is_active = django_filters.BooleanFilter(
        field_name="is_active",
        help_text="Filter by enrollment status (active/inactive)",
    )
    completed = django_filters.BooleanFilter(
        field_name="completed", help_text="Filter by course completion status"
    )
    certificate_issued = django_filters.BooleanFilter(
        field_name="certificate_issued", help_text="Filter by certificate issued status"
    )
    rating = django_filters.NumberFilter(
        field_name="rating",
        lookup_expr="exact",
        help_text="Filter by exact rating (1-5)",
    )
    rating_min = django_filters.NumberFilter(
        field_name="rating", lookup_expr="gte", help_text="Filter by minimum rating"
    )
    rating_max = django_filters.NumberFilter(
        field_name="rating", lookup_expr="lte", help_text="Filter by maximum rating"
    )
    has_rating = django_filters.BooleanFilter(
        method="filter_has_rating", help_text="Filter by presence of rating"
    )
    enrolled_after = django_filters.DateTimeFilter(
        field_name="enrolled_at",
        lookup_expr="gte",
        help_text="Filter by enrollment date (on or after)",
    )
    enrolled_before = django_filters.DateTimeFilter(
        field_name="enrolled_at",
        lookup_expr="lte",
        help_text="Filter by enrollment date (on or before)",
    )
    completed_after = django_filters.DateTimeFilter(
        field_name="completed_at",
        lookup_expr="gte",
        help_text="Filter by completion date (on or after)",
    )
    completed_before = django_filters.DateTimeFilter(
        field_name="completed_at",
        lookup_expr="lte",
        help_text="Filter by completion date (on or before)",
    )
    has_review = django_filters.BooleanFilter(
        method="filter_has_review", help_text="Filter by presence of review"
    )

    class Meta:
        model = Enrollment
        fields = ["course", "is_active", "completed", "certificate_issued", "rating"]

    def filter_has_rating(self, queryset, name, value):
        if value:
            return queryset.filter(rating__isnull=False)
        return queryset.filter(rating__isnull=True)

    def filter_has_review(self, queryset, name, value):
        if value:
            return queryset.exclude(models.Q(review__isnull=True) | models.Q(review=""))
        return queryset.filter(models.Q(review__isnull=True) | models.Q(review=""))


class LessonProgressFilter(django_filters.FilterSet):
    """
    Filter class for querying and filtering LessonProgress records in the WSS backend system.

    Purpose:
        Provides a flexible, API-friendly filtering interface for LessonProgress model queryset operations.
        Enables REST API endpoints to track and filter individual lesson viewing progress data without
        requiring manual query construction or complex filtering logic.

    Functionality:
        - Filters lesson progress by enrollment and lesson relationships
        - Filters by course through lesson foreign key relationships
        - Filters by lesson completion status
        - Supports watch duration filtering with range queries (minimum and maximum)
        - Supports temporal filtering for last watched date with range queries

    Integration:
        - Automatically integrated with DRF ViewSets via FilterBackend configuration
        - Works seamlessly with LessonProgress model fields and relationships (enrollment, lesson, last_watched)
        - Complements EnrollmentFilter for granular tracking of student learning progress
        - Provides standardized filter definitions and help text for API documentation and schema generation
        - Enables efficient querying of progress metrics for analytics, reporting, and student tracking

    Attributes:
        enrollment: Filter by Enrollment ID
        lesson: Filter by Lesson ID
        lesson__course: Filter by Course ID (through lesson relationship)
        completed: Filter by lesson completion status
        watched_duration_min: Filter by minimum watched duration (gte)
        watched_duration_max: Filter by maximum watched duration (lte)
        last_watched_after: Filter by last watched date (on or after)
        last_watched_before: Filter by last watched date (on or before)
    """

    enrollment = django_filters.NumberFilter(
        field_name="enrollment", help_text="Filter by Enrollment ID"
    )
    lesson = django_filters.NumberFilter(
        field_name="lesson", help_text="Filter by Lesson ID"
    )
    lesson__course = django_filters.NumberFilter(
        field_name="lesson__course", help_text="Filter by Course ID (through lesson)"
    )
    completed = django_filters.BooleanFilter(
        field_name="completed", help_text="Filter by lesson completion status"
    )
    watched_duration_min = django_filters.NumberFilter(
        field_name="watched_duration",
        lookup_expr="gte",
        help_text="Filter by minimum watched duration (minutes)",
    )
    watched_duration_max = django_filters.NumberFilter(
        field_name="watched_duration",
        lookup_expr="lte",
        help_text="Filter by maximum watched duration (minutes)",
    )
    last_watched_after = django_filters.DateTimeFilter(
        field_name="last_watched_at",
        lookup_expr="gte",
        help_text="Filter by last watched date (on or after)",
    )
    last_watched_before = django_filters.DateTimeFilter(
        field_name="last_watched_at",
        lookup_expr="lte",
        help_text="Filter by last watched date (on or before)",
    )

    class Meta:
        model = LessonProgress
        fields = ["enrollment", "lesson", "completed"]
