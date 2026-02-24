"""
Filters for the videos module.

This module provides filter classes for video and lesson resources using django-filter.
Filters enable API consumers to search and filter lesson and video data through query
parameters in GET requests, supporting features like course-based filtering, duration
ranges, preview status, and processing state.

Available filters:
    - LessonFilter: Comprehensive filtering for lesson resources (10 filters)
    - VideoFilter: Filtering for video resources (8 filters)

Key Features:
    - ForeignKey navigation (course, course__slug)
    - Range filtering (duration, file_size, order)
    - Boolean filters (is_free_preview, is_processed)
    - Date filtering (created_at ranges)
    - Search capabilities (title, description)

Usage Example:
    GET /api/lessons/?course=1&is_free_preview=true
    GET /api/lessons/?duration_min=10&duration_max=30
    GET /api/videos/?is_processed=true&file_size_max=500000000
    GET /api/lessons/?course__slug=python-basics&order_min=1&order_max=5
"""

import django_filters
from .models import Lesson, Video


class LessonFilter(django_filters.FilterSet):
    """
    FilterSet for Lesson model with comprehensive filtering options.
    
    Provides 10 filters for lesson resources, enabling course-based navigation,
    duration ranges, preview filtering, and lesson ordering. Supports API
    consumers in discovering and filtering course content efficiently.
    
    Available Filters:
        1. course (NumberFilter): Filter by course ID (exact match)
        2. course__slug (CharFilter): Filter by course slug (case-insensitive)
        3. is_free_preview (BooleanFilter): Filter by preview status
        4. order (NumberFilter): Filter by specific lesson order
        5. order_min (NumberFilter): Minimum lesson order (gte)
        6. order_max (NumberFilter): Maximum lesson order (lte)
        7. duration_min (NumberFilter): Minimum duration in minutes (gte)
        8. duration_max (NumberFilter): Maximum duration in minutes (lte)
        9. search (CharFilter): Search in title and description (icontains)
        10. Meta ordering: Support for ordering by order, duration, created_at
    
    Query Examples:
        /api/lessons/?course=1                      # All lessons in course 1
        /api/lessons/?course__slug=python-basics    # Lessons by course slug
        /api/lessons/?is_free_preview=true          # Only free preview lessons
        /api/lessons/?order_min=1&order_max=5       # First 5 lessons
        /api/lessons/?duration_min=30               # Lessons 30+ minutes
        /api/lessons/?search=django                 # Search in title/description
    
    ForeignKey Navigation:
        The filter uses Django's double underscore notation to navigate relationships:
        course__slug → Lesson.course.slug (follows ForeignKey relationship)
    
    Meta:
        model: Lesson
        fields: ['course', 'is_free_preview', 'order']
    """
    
    # Course filters (ForeignKey navigation)
    course = django_filters.NumberFilter(
        field_name='course',
        help_text='Filter by course ID (exact match)'
    )
    
    course__slug = django_filters.CharFilter(
        field_name='course__slug',
        lookup_expr='iexact',
        help_text='Filter by course slug (case-insensitive, e.g., "python-basics")'
    )
    
    # Preview filter
    is_free_preview = django_filters.BooleanFilter(
        field_name='is_free_preview',
        help_text='Filter by preview status (true/false)'
    )
    
    # Order filters (range support)
    order = django_filters.NumberFilter(
        field_name='order',
        help_text='Filter by specific lesson order number'
    )
    
    order_min = django_filters.NumberFilter(
        field_name='order',
        lookup_expr='gte',
        help_text='Minimum lesson order (greater than or equal)'
    )
    
    order_max = django_filters.NumberFilter(
        field_name='order',
        lookup_expr='lte',
        help_text='Maximum lesson order (less than or equal)'
    )
    
    # Duration filters (range support)
    duration_min = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='gte',
        help_text='Minimum duration in minutes (e.g., 30 for 30+ minute lessons)'
    )
    
    duration_max = django_filters.NumberFilter(
        field_name='duration',
        lookup_expr='lte',
        help_text='Maximum duration in minutes (e.g., 60 for lessons up to 1 hour)'
    )
    
    # Search filter (title + description)
    search = django_filters.CharFilter(
        method='filter_search',
        help_text='Search in lesson title and description (case-insensitive)'
    )
    
    class Meta:
        model = Lesson
        fields = ['course', 'is_free_preview', 'order']
    
    def filter_search(self, queryset, name, value):
        """
        Custom filter method for searching across multiple fields.
        
        Searches in both title and description fields using case-insensitive
        contains lookup (icontains). This allows users to find lessons by
        keyword without knowing the exact field.
        
        Args:
            queryset: The current queryset being filtered
            name: The filter field name (not used in this implementation)
            value: The search term provided by the user
            
        Returns:
            QuerySet: Filtered queryset matching the search criteria
        
        Example:
            /api/lessons/?search=django
            Returns lessons with "django" in title OR description
        
        Implementation Note:
            Uses Q objects to combine multiple field lookups with OR logic:
            Q(title__icontains=value) | Q(description__icontains=value)
        """
        from django.db.models import Q
        
        if not value:
            return queryset
        
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )


class VideoFilter(django_filters.FilterSet):
    """
    FilterSet for Video model with processing and file-based filtering.
    
    Provides 8 filters for video resources, focusing on processing status,
    file characteristics (size, upload date), and search capabilities.
    Enables instructor dashboards and admin panels to filter videos efficiently.
    
    Available Filters:
        1. is_processed (BooleanFilter): Filter by processing status
        2. file_size_min (NumberFilter): Minimum file size in bytes (gte)
        3. file_size_max (NumberFilter): Maximum file size in bytes (lte)
        4. created_at_after (DateFilter): Videos created after date (gte)
        5. created_at_before (DateFilter): Videos created before date (lte)
        6. search (CharFilter): Search in video title (icontains)
        7. Meta ordering: Support for ordering by created_at, file_size
        8. Meta fields: Direct access to is_processed
    
    Query Examples:
        /api/videos/?is_processed=true                          # Only processed videos
        /api/videos/?file_size_max=500000000                    # Videos under 500MB
        /api/videos/?created_at_after=2026-01-01                # Videos from 2026
        /api/videos/?search=introduction                        # Search by title
        /api/videos/?is_processed=false&created_at_after=2026-02-01  # Recent unprocessed
    
    File Size Notes:
        - file_size is stored in bytes in the database
        - Use file_size_max=524288000 for 500MB limit (500 * 1024 * 1024)
        - Frontend should convert MB to bytes before sending request
    
    Meta:
        model: Video
        fields: ['is_processed']
    """
    
    # Processing status filter
    is_processed = django_filters.BooleanFilter(
        field_name='is_processed',
        help_text='Filter by video processing status (true = ready, false = processing)'
    )
    
    # File size filters (range support in bytes)
    file_size_min = django_filters.NumberFilter(
        field_name='file_size',
        lookup_expr='gte',
        help_text='Minimum file size in bytes (e.g., 10485760 for 10MB)'
    )
    
    file_size_max = django_filters.NumberFilter(
        field_name='file_size',
        lookup_expr='lte',
        help_text='Maximum file size in bytes (e.g., 524288000 for 500MB)'
    )
    
    # Date filters (when video was uploaded)
    created_at_after = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='gte',
        help_text='Videos created after this date (YYYY-MM-DD format)'
    )
    
    created_at_before = django_filters.DateFilter(
        field_name='created_at',
        lookup_expr='lte',
        help_text='Videos created before this date (YYYY-MM-DD format)'
    )
    
    # Search filter (title only, videos don't have description)
    search = django_filters.CharFilter(
        field_name='title',
        lookup_expr='icontains',
        help_text='Search in video title (case-insensitive)'
    )
    
    class Meta:
        model = Video
        fields = ['is_processed']