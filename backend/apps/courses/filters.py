"""
Filters for the courses module.

This module provides advanced filtering capabilities for course queries,
enabling users to search and filter courses by multiple criteria including
category, instructor, difficulty, price range, and publication status.

Features:
    - Category filtering (by ID or slug)
    - Instructor filtering (by ID or username)
    - Difficulty level filtering
    - Price range filtering (min/max)
    - Free courses filtering (price == 0)
    - Publication status filtering (with intelligent defaults)
"""
import django_filters

from .models import Course


class CourseFilter(django_filters.FilterSet):
    """
    FilterSet for Course model.
    
    Provides advanced filtering capabilities for course queries, enabling users to search and
    filter courses by multiple criteria with support for both exact and partial matching.
    
    Attributes:
        category: Filter courses by category ID (exact match)
        category__slug: Filter courses by category slug (exact match, case-sensitive)
        instructor: Filter courses by instructor user ID (exact match)
        instructor__username: Filter courses by instructor username (partial match, case-insensitive)
        difficulty: Filter courses by difficulty level (BEG=Beginner, INT=Intermediate, ADV=Advanced)
        is_published: Filter by publication status (published/unpublished)
        price_min: Filter courses with price >= specified value
        price_max: Filter courses with price <= specified value
        is_free: Filter only free courses (price == 0)
    
    Filtering combines multiple criteria using AND logic. Non-staff users will only see
    published courses regardless of is_published filter setting.
    """


    category = django_filters.NumberFilter(field_name='category', help_text='Filter by category ID (exact match)')
    category__slug = django_filters.CharFilter(field_name='category__slug', lookup_expr='exact', help_text='Filter by category slug (exact match, e.g., "web-development")')
    instructor = django_filters.NumberFilter(field_name='instructor', help_text='Filter by instructor user ID (exact match)')
    instructor__username = django_filters.CharFilter(field_name='instructor__username', lookup_expr='icontains', help_text='Filter by instructor username (partial match, case-insensitive)')
    difficulty = django_filters.ChoiceFilter(choices=Course.DifficultyLevel.choices, help_text='Filter by difficulty level (BEG, INT, or ADV)')
    is_published = django_filters.BooleanFilter(field_name='is_published', help_text='Filter by publication status (true/false). Non-staff users always see only published courses.')
    price_min = django_filters.NumberFilter(field_name='price', lookup_expr='gte', help_text='Filter courses with price greater than or equal to this value')
    price_max = django_filters.NumberFilter(field_name='price', lookup_expr='lte', help_text='Filter courses with price less than or equal to this value')
    is_free = django_filters.BooleanFilter(method='filter_is_free', help_text='Filter free courses (price == 0). Use ?is_free=true')


    class Meta:
        model = Course
        fields = [
            'category',
            'category__slug',
            'instructor',
            'instructor__username',
            'difficulty',
            'is_published',
            'price_min',
            'price_max',
            'is_free',         
        ]

    def filter_is_free(self, queryset, name, value):
        if value is True:
            return queryset.filter(price=0)
        elif value is False:
            return queryset.filter(price__gt=0)

        return queryset
