"""
Serializers for Course and Category management.

This module contains serializers for:
- Category CRUD operations
- Course management with different levels of detail
- Nested relationships with User (instructor) and Category
- Business logic validation for course creation

All serializers include proper validation and optimization.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.users.serializers import UserListSerializer

from .models import Category, Course, Module, generate_unique_slug


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for Category CRUD operations.

    Handles automatic slug generation from name if not provided.
    """

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "slug": {"required": False},  # Optional, auto-generated if empty
        }

    def update(self, instance, validated_data):
        """Regenerate a unique slug if name changed and slug not provided."""
        if "name" in validated_data and not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_slug(
                Category, validated_data["name"], exclude_pk=instance.pk
            )
        return super().update(instance, validated_data)


class CategoryListSerializer(serializers.ModelSerializer):
    """
    Minimal category serializer for list views and nested relationships.
    """

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class CourseListSerializer(serializers.ModelSerializer):
    """
    Minimal course serializer for list views.

    Includes basic information and computed fields for performance.
    """

    instructor_name = serializers.CharField(
        source="instructor.get_full_name", read_only=True
    )
    category_name = serializers.CharField(source="category.name", read_only=True)
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "thumbnail",
            "price",
            "difficulty",
            "duration_hours",
            "is_published",
            "instructor_name",
            "category_name",
            "enrolled_count",
            "created_at",
        ]

    def get_enrolled_count(self, obj: Course) -> int:
        """Return number of active enrollments.

        Prefers the ``annotated_enrolled_count`` annotation set by the viewset
        ``get_queryset`` (avoids an N+1 COUNT per row); falls back to a query
        when the serializer is used outside that queryset.
        """
        count = getattr(obj, "annotated_enrolled_count", None)
        if count is not None:
            return count
        return obj.enrollments.filter(is_active=True).count()


class CourseDetailSerializer(serializers.ModelSerializer):
    """
    Detailed course serializer for single course views.

    Includes nested relationships and computed fields.
    """

    instructor = UserListSerializer(read_only=True)
    category = CategoryListSerializer(read_only=True)
    enrolled_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()
    lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "instructor",
            "category",
            "thumbnail",
            "price",
            "difficulty",
            "is_published",
            "duration_hours",
            "what_you_will_learn",
            "requirements",
            "enrolled_count",
            "is_enrolled",
            "lessons_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_enrolled_count(self, obj: Course) -> int:
        """Return number of active enrollments.

        Prefers the ``annotated_enrolled_count`` annotation set by the viewset
        ``get_queryset``; falls back to a query when unavailable.
        """
        count = getattr(obj, "annotated_enrolled_count", None)
        if count is not None:
            return count
        return obj.enrollments.filter(is_active=True).count()

    def get_is_enrolled(self, obj: Course) -> bool:
        """Check if current user is enrolled in this course."""
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(user=request.user, is_active=True).exists()
        return False

    def get_lessons_count(self, obj: Course) -> int:
        """Return total number of lessons in this course.

        Prefers the ``annotated_lessons_count`` annotation set by the viewset
        ``get_queryset``; falls back to a query when unavailable.
        """
        count = getattr(obj, "annotated_lessons_count", None)
        if count is not None:
            return count
        return obj.lessons.count()


class CourseCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new courses.

    Includes business logic validation and automatic field population.
    """

    class Meta:
        model = Course
        fields = [
            "title",
            "slug",
            "description",
            "category",
            "thumbnail",
            "price",
            "difficulty",
            "duration_hours",
            "what_you_will_learn",
            "requirements",
        ]
        extra_kwargs = {
            "slug": {"required": False},
        }

    def validate_category(self, value):
        """Ensure category is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot create course in inactive category."
            )
        return value


class CourseUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating existing courses.

    Only course owners (instructors) can update their courses.
    """

    class Meta:
        model = Course
        fields = [
            "title",
            "slug",
            "description",
            "category",
            "thumbnail",
            "price",
            "difficulty",
            "duration_hours",
            "what_you_will_learn",
            "requirements",
            "is_published",
        ]
        extra_kwargs = {
            "slug": {"required": False},
        }

    def validate_category(self, value):
        """Ensure category is active."""
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot assign course to inactive category."
            )
        return value

    def validate(self, data):
        """Block publishing without lessons and freeze price on enrolled courses.

        Authorization (ownership) is enforced by the permission classes
        (IsCourseOwnerOrReadOnly → 403), not here.
        """
        if (
            data.get("is_published")
            and self.instance
            and not self.instance.lessons.exists()
        ):
            raise serializers.ValidationError(
                {"is_published": "Cannot publish a course without lessons."}
            )

        # Soft-freeze: once a course has active enrollments, its sticker price
        # cannot be changed through the normal update path. Use the dedicated
        # adjust-price action (audited, requires confirmation).
        if (
            "price" in data
            and self.instance
            and data["price"] != self.instance.price
            and self.instance.get_enrolled_count() > 0
        ):
            raise serializers.ValidationError(
                {
                    "price": (
                        "Cannot change price while the course has active "
                        "enrollments. Use the adjust-price action."
                    )
                }
            )
        return data

    def update(self, instance, validated_data):
        """Regenerate a unique slug if title changed and slug not provided."""
        if "title" in validated_data and not validated_data.get("slug"):
            validated_data["slug"] = generate_unique_slug(
                Course, validated_data["title"], exclude_pk=instance.pk
            )

        return super().update(instance, validated_data)


class AdjustPriceSerializer(serializers.Serializer):
    """Input for the audited adjust-price action.

    Attributes:
        new_price: The new sticker price (>= 0).
        confirm: Must be true to adjust the price of a course that already
            has active enrollments.
    """

    new_price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.00"),
    )
    confirm = serializers.BooleanField(default=False)


class ModuleSerializer(serializers.ModelSerializer):
    """
    Serializer for Module CRUD operations.

    Enforces:
        - Uniqueness of (course, order) within create and order-changing
          updates, via DRF's built-in UniqueTogetherValidator (declared
          through Model Meta).

    Note:
        Ownership (only the course instructor may create/update a module)
        is enforced by ``IsModuleCourseInstructorOrReadOnly`` at the
        permission layer, not here — authz failures return 403, not 400
        (#122; same anti-pattern already fixed for courses in #66).
    """

    lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            "id",
            "course",
            "title",
            "description",
            "order",
            "lessons_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_lessons_count(self, obj: Module) -> int:
        """Return number of lessons inside this module."""
        return obj.lessons.count()


class ModuleWithLessonsSerializer(serializers.ModelSerializer):
    """
    Read-only Module serializer that nests its lessons.

    Used in the nested course action (GET /api/courses/{id}/modules/) to
    deliver a hierarchical view of the course curriculum.
    """

    lessons = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            "id",
            "course",
            "title",
            "description",
            "order",
            "lessons",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_lessons(self, obj: Module) -> list:
        """Return ordered lessons for this module using LessonListSerializer."""
        from apps.videos.serializers import LessonListSerializer

        lessons = obj.lessons.all().order_by("order")
        return LessonListSerializer(lessons, many=True, context=self.context).data
