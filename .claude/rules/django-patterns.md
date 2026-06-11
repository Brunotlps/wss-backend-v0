# Django Patterns & Conventions

## Models

### Standard Model Structure

```python
from django.db import models
from apps.core.models import TimeStampedModel


class MyModel(TimeStampedModel):
    """Brief model description.
    
    Attributes:
        field1: Description
        field2: Description
    """
    
    # Field organization:
    # 1. Primary fields
    # 2. Foreign keys
    # 3. Many-to-Many
    # 4. Metadata fields (created_at from TimeStampedModel)
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='my_models'
    )
    
    tags = models.ManyToManyField('Tag', blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'My Model'
        verbose_name_plural = 'My Models'
        unique_together = [['user', 'slug']]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def get_absolute_url(self) -> str:
        """Return absolute URL for this object."""
        from django.urls import reverse
        return reverse('mymodel-detail', kwargs={'pk': self.pk})
```

### Field Best Practices

```python
# ✅ GOOD: Explicit choices with proper structure
class Enrollment(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE
    )

# ❌ BAD: Hardcoded strings, no type safety
class Enrollment(models.Model):
    status = models.CharField(max_length=20)
```

### Query Optimization

```python
# ✅ GOOD: Use select_related for ForeignKey
courses = Course.objects.select_related('instructor').all()

# ✅ GOOD: Use prefetch_related for reverse FK and M2M
courses = Course.objects.prefetch_related('videos', 'enrollments').all()

# ✅ GOOD: Combine both
courses = Course.objects.select_related(
    'instructor'
).prefetch_related(
    'videos',
    'enrollments__user'
).all()

# ❌ BAD: N+1 query problem
courses = Course.objects.all()
for course in courses:
    print(course.instructor.name)  # Extra query per course!
```

### Custom Managers

```python
from django.db import models


class ActiveManager(models.Manager):
    """Manager for active objects only."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class Course(TimeStampedModel):
    is_active = models.BooleanField(default=True)
    
    objects = models.Manager()  # Default manager
    active = ActiveManager()    # Custom manager
    
    class Meta:
        default_manager_name = 'objects'


# Usage
all_courses = Course.objects.all()      # All courses
active_courses = Course.active.all()    # Only active
```

## Views (DRF)

### ViewSet Structure

```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Course
from .serializers import (
    CourseSerializer,
    CourseDetailSerializer,
    CourseCreateSerializer
)
from .permissions import IsCourseInstructorOrReadOnly


class CourseViewSet(viewsets.ModelViewSet):
    """CRUD operations for Courses.
    
    Permissions:
        - List/Retrieve: Any
        - Create: Authenticated
        - Update/Delete: Instructor only
    
    Endpoints:
        GET    /api/courses/          - List courses
        POST   /api/courses/          - Create course
        GET    /api/courses/{id}/     - Retrieve course
        PATCH  /api/courses/{id}/     - Update course
        DELETE /api/courses/{id}/     - Delete course
        POST   /api/courses/{id}/publish/ - Custom action
    """
    
    permission_classes = [IsAuthenticated, IsCourseInstructorOrReadOnly]
    
    def get_queryset(self):
        """Optimize queryset with select/prefetch."""
        return Course.objects.select_related(
            'instructor'
        ).prefetch_related(
            'videos',
            'enrollments'
        )
    
    def get_serializer_class(self):
        """Return serializer based on action."""
        if self.action == 'create':
            return CourseCreateSerializer
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    def perform_create(self, serializer):
        """Set instructor to current user."""
        serializer.save(instructor=self.request.user)
    
    @transaction.atomic
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publish course (custom action)."""
        course = self.get_object()
        
        if course.videos.count() == 0:
            return Response(
                {"detail": "Cannot publish course without videos"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        course.is_published = True
        course.save(update_fields=['is_published'])
        
        return Response(
            {"detail": "Course published successfully"},
            status=status.HTTP_200_OK
        )
```

### APIView for Custom Logic

```python
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


class EnrollUserView(APIView):
    """Enroll user in a course."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, course_id):
        """Enroll current user in course."""
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already enrolled
        if Enrollment.objects.filter(
            user=request.user,
            course=course
        ).exists():
            return Response(
                {"detail": "Already enrolled"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create enrollment
        enrollment = Enrollment.objects.create(
            user=request.user,
            course=course
        )
        
        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED
        )
```

## Serializers

### Serializer Organization

```python
from rest_framework import serializers
from .models import Course, Video


class CourseSerializer(serializers.ModelSerializer):
    """List serializer for Course."""
    
    instructor_name = serializers.CharField(
        source='instructor.get_full_name',
        read_only=True
    )
    video_count = serializers.IntegerField(
        source='videos.count',
        read_only=True
    )
    is_free = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id',
            'name',
            'slug',
            'price',
            'instructor',
            'instructor_name',
            'video_count',
            'is_free',
            'created_at',
        ]
        read_only_fields = ['created_at', 'slug']


class CourseDetailSerializer(CourseSerializer):
    """Detail serializer with nested videos."""
    
    videos = serializers.SerializerMethodField()
    
    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + [
            'description',
            'videos',
        ]
    
    def get_videos(self, obj):
        """Return videos ordered by order field."""
        videos = obj.videos.all().order_by('order')
        return VideoSerializer(videos, many=True).data


class CourseCreateSerializer(serializers.ModelSerializer):
    """Create serializer with custom validation."""
    
    class Meta:
        model = Course
        fields = ['name', 'description', 'price']
    
    def validate_price(self, value):
        """Ensure price is non-negative."""
        if value < 0:
            raise serializers.ValidationError(
                "Price cannot be negative"
            )
        return value
    
    def validate(self, attrs):
        """Cross-field validation."""
        if attrs.get('price') == 0 and not attrs.get('description'):
            raise serializers.ValidationError(
                "Free courses must have a description"
            )
        return attrs
```

### Nested Serializers

```python
class VideoSerializer(serializers.ModelSerializer):
    """Serializer for Video objects."""
    
    class Meta:
        model = Video
        fields = ['id', 'title', 'order', 'duration']


class CourseWithVideosSerializer(serializers.ModelSerializer):
    """Course with nested videos (read-only)."""
    
    videos = VideoSerializer(many=True, read_only=True)
    
    class Meta:
        model = Course
        fields = ['id', 'name', 'videos']


class CourseCreateWithVideosSerializer(serializers.ModelSerializer):
    """Course creation allowing video creation."""
    
    videos = VideoSerializer(many=True, required=False)
    
    class Meta:
        model = Course
        fields = ['name', 'price', 'videos']
    
    def create(self, validated_data):
        """Create course and nested videos."""
        videos_data = validated_data.pop('videos', [])
        course = Course.objects.create(**validated_data)
        
        for video_data in videos_data:
            Video.objects.create(course=course, **video_data)
        
        return course
```

## Permissions

### Custom Permission Classes

```python
from rest_framework import permissions


class IsCourseInstructor(permissions.BasePermission):
    """Permission: Only course instructor can modify."""
    
    message = "You must be the course instructor to perform this action."
    
    def has_object_permission(self, request, view, obj):
        """Check if user is the instructor."""
        return obj.instructor == request.user


class IsCourseInstructorOrReadOnly(permissions.BasePermission):
    """Read for all, write for instructor only."""
    
    def has_object_permission(self, request, view, obj):
        """Allow read for all, write for instructor."""
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.instructor == request.user


class IsEnrolled(permissions.BasePermission):
    """Check if user is enrolled in course."""
    
    def has_object_permission(self, request, view, obj):
        """Check enrollment with Redis cache."""
        from django.core.cache import cache
        
        cache_key = f'enrollment:{request.user.id}:{obj.course_id}'
        
        is_enrolled = cache.get(cache_key)
        if is_enrolled is not None:
            return is_enrolled
        
        is_enrolled = Enrollment.objects.filter(
            user=request.user,
            course_id=obj.course_id
        ).exists()
        
        cache.set(cache_key, is_enrolled, timeout=900)  # 15 min
        return is_enrolled
```

## Signals

### Signal Best Practices

```python
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.core.cache import cache

from .models import Enrollment, Certificate


@receiver(post_save, sender=Enrollment)
def create_certificate_on_completion(sender, instance, created, **kwargs):
    """Create certificate when enrollment is completed.
    
    Note: Lightweight operation. Heavy tasks delegated to Celery.
    """
    if instance.completed and not created:
        # Check if certificate already exists
        if not Certificate.objects.filter(enrollment=instance).exists():
            # Use Celery for PDF generation (heavy task)
            from apps.certificates.tasks import generate_certificate_async
            
            certificate = Certificate.objects.create(
                enrollment=instance,
                issued_at=timezone.now()
            )
            generate_certificate_async.delay(certificate.id)


@receiver(post_save, sender=Enrollment)
def invalidate_enrollment_cache(sender, instance, **kwargs):
    """Invalidate Redis cache on enrollment change."""
    cache_key = f'enrollment:{instance.user_id}:{instance.course_id}'
    cache.delete(cache_key)


@receiver(pre_delete, sender=Enrollment)
def prevent_enrollment_deletion_if_completed(sender, instance, **kwargs):
    """Prevent deletion of completed enrollments."""
    if instance.completed:
        raise ValueError("Cannot delete completed enrollment")
```

## URLs

### URL Configuration

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import CourseViewSet, EnrollUserView

router = DefaultRouter()
router.register(r'courses', CourseViewSet, basename='course')

urlpatterns = [
    path('', include(router.urls)),
    path('courses/<int:course_id>/enroll/', EnrollUserView.as_view(), name='enroll'),
]
```

## Admin

### Custom Admin

```python
from django.contrib import admin
from .models import Course, Video


class VideoInline(admin.TabularInline):
    """Inline video editing in course admin."""
    model = Video
    extra = 1
    fields = ['title', 'order', 'duration', 'file']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Admin for Course model."""
    
    list_display = ['name', 'instructor', 'price', 'is_published', 'created_at']
    list_filter = ['is_published', 'created_at']
    search_fields = ['name', 'instructor__email']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [VideoInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description')
        }),
        ('Pricing', {
            'fields': ('price',)
        }),
        ('Instructor', {
            'fields': ('instructor',)
        }),
        ('Status', {
            'fields': ('is_published',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Optimize admin queryset."""
        return super().get_queryset(request).select_related('instructor')
```

## Checklist

Before committing Django code:

- [ ] Models inherit from TimeStampedModel
- [ ] All ForeignKeys have explicit `related_name`
- [ ] Queries use select_related/prefetch_related
- [ ] ViewSets use appropriate permission classes
- [ ] Serializers have proper validation
- [ ] Custom permissions are well-documented
- [ ] Signals are lightweight (heavy tasks → Celery)
- [ ] Admin is optimized with list_select_related
