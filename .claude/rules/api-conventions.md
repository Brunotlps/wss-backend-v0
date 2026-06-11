# API Conventions

## REST Principles

### Resource Naming

```
# ✅ GOOD: Plural nouns for collections
GET    /api/courses/
POST   /api/courses/
GET    /api/courses/{id}/
PATCH  /api/courses/{id}/
DELETE /api/courses/{id}/

# ✅ GOOD: Nested resources for relationships
GET    /api/courses/{id}/videos/
POST   /api/courses/{id}/videos/
GET    /api/courses/{id}/enrollments/

# ❌ BAD: Verbs in URLs
POST   /api/courses/create/
GET    /api/courses/get-all/
POST   /api/users/login/         # Exception: auth endpoints
```

### HTTP Methods

```
GET     - Retrieve resource(s)      (Safe, Idempotent)
POST    - Create new resource       (Not safe, Not idempotent)
PUT     - Replace entire resource   (Not safe, Idempotent)
PATCH   - Partial update            (Not safe, Not idempotent)
DELETE  - Remove resource           (Not safe, Idempotent)
```

### Custom Actions

```python
# ✅ GOOD: Use @action decorator for non-CRUD operations
@action(detail=True, methods=['post'])
def publish(self, request, pk=None):
    """POST /api/courses/{id}/publish/"""
    pass

@action(detail=False, methods=['get'])
def popular(self, request):
    """GET /api/courses/popular/"""
    pass

# ❌ BAD: Creating separate views for simple actions
class PublishCourseView(APIView):  # Unnecessary
    pass
```

## Response Format

### Success Responses

```json
// List (200 OK)
{
    "count": 42,
    "next": "http://api.example.com/courses/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Django Course",
            "price": "99.00"
        }
    ]
}

// Detail (200 OK)
{
    "id": 1,
    "name": "Django Course",
    "description": "Learn Django",
    "price": "99.00",
    "instructor": {
        "id": 5,
        "name": "John Doe"
    },
    "videos": [
        {"id": 1, "title": "Introduction"}
    ]
}

// Create (201 Created)
{
    "id": 1,
    "name": "Django Course",
    "created_at": "2026-04-07T10:00:00Z"
}

// Update (200 OK)
{
    "id": 1,
    "name": "Updated Course Name"
}

// Delete (204 No Content)
// Empty body
```

### Error Responses

```json
// 400 Bad Request - Validation errors
{
    "detail": "Validation failed",
    "errors": {
        "email": ["This field is required."],
        "price": ["Ensure this value is greater than or equal to 0."]
    }
}

// 401 Unauthorized
{
    "detail": "Authentication credentials were not provided."
}

// 403 Forbidden
{
    "detail": "You do not have permission to perform this action."
}

// 404 Not Found
{
    "detail": "Not found."
}

// 409 Conflict
{
    "detail": "User already enrolled in this course."
}

// 500 Internal Server Error
{
    "detail": "An error occurred on the server."
}
```

## Status Codes

### Common Usage

```python
from rest_framework import status

# Success
status.HTTP_200_OK              # GET, PATCH, PUT
status.HTTP_201_CREATED         # POST (resource created)
status.HTTP_204_NO_CONTENT      # DELETE, POST (no data)

# Client Errors
status.HTTP_400_BAD_REQUEST     # Validation error
status.HTTP_401_UNAUTHORIZED    # Not authenticated
status.HTTP_403_FORBIDDEN       # Not authorized
status.HTTP_404_NOT_FOUND       # Resource doesn't exist
status.HTTP_409_CONFLICT        # Business logic conflict
status.HTTP_422_UNPROCESSABLE_ENTITY  # Semantic error

# Server Errors
status.HTTP_500_INTERNAL_SERVER_ERROR
status.HTTP_503_SERVICE_UNAVAILABLE
```

### Custom Status Codes

```python
# ✅ GOOD: Appropriate status for business rules
def create(self, request):
    course = get_object_or_404(Course, id=request.data['course_id'])
    
    # User already enrolled - conflict
    if Enrollment.objects.filter(user=request.user, course=course).exists():
        return Response(
            {"detail": "Already enrolled"},
            status=status.HTTP_409_CONFLICT
        )
    
    # Paid course without payment - payment required
    if course.price > 0 and not has_valid_payment(request.user, course):
        return Response(
            {"detail": "Payment required"},
            status=status.HTTP_402_PAYMENT_REQUIRED
        )
    
    enrollment = Enrollment.objects.create(user=request.user, course=course)
    return Response(
        EnrollmentSerializer(enrollment).data,
        status=status.HTTP_201_CREATED
    )
```

## Filtering & Pagination

### Query Parameters

```
# Filtering
GET /api/courses/?price=0                  # Exact match
GET /api/courses/?price__gte=50            # Greater than or equal
GET /api/courses/?instructor=5             # Foreign key
GET /api/courses/?is_published=true        # Boolean
GET /api/courses/?search=django            # Full-text search

# Ordering
GET /api/courses/?ordering=-created_at     # Descending
GET /api/courses/?ordering=price           # Ascending
GET /api/courses/?ordering=price,-name     # Multiple fields

# Pagination
GET /api/courses/?page=2                   # Page number
GET /api/courses/?limit=20&offset=40       # Limit-offset
```

### FilterSet Configuration

```python
from django_filters import rest_framework as filters
from .models import Course


class CourseFilter(filters.FilterSet):
    """Filter for Course queryset."""
    
    price_min = filters.NumberFilter(field_name='price', lookup_expr='gte')
    price_max = filters.NumberFilter(field_name='price', lookup_expr='lte')
    is_free = filters.BooleanFilter(method='filter_is_free')
    
    class Meta:
        model = Course
        fields = {
            'name': ['exact', 'icontains'],
            'instructor': ['exact'],
            'is_published': ['exact'],
        }
    
    def filter_is_free(self, queryset, name, value):
        """Filter free courses (price = 0)."""
        if value:
            return queryset.filter(price=0)
        return queryset.exclude(price=0)


class CourseViewSet(viewsets.ModelViewSet):
    filterset_class = CourseFilter
    filter_backends = [
        filters.DjangoFilterBackend,
        SearchFilter,
        OrderingFilter
    ]
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'name']
    ordering = ['-created_at']
```

## Authentication & Authorization

### JWT Authentication

```python
# settings/base.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
}

# Views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
```

### Authentication Headers

```bash
# ✅ GOOD: Bearer token in Authorization header
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."

# ❌ BAD: Token in URL or body
curl /api/courses/?token=abc123
```

### Permission Composition

```python
from rest_framework.permissions import IsAuthenticated
from .permissions import IsCourseInstructor, IsEnrolled


class VideoViewSet(viewsets.ModelViewSet):
    """Videos accessible only to enrolled users."""
    
    permission_classes = [IsAuthenticated, IsEnrolled]
    
    def get_permissions(self):
        """Update/Delete requires instructor permission."""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsCourseInstructor()]
        return [IsAuthenticated(), IsEnrolled()]
```

## Versioning

### URL Path Versioning

```python
# settings/base.py
REST_FRAMEWORK = {
    'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
    'DEFAULT_VERSION': 'v1',
    'ALLOWED_VERSIONS': ['v1', 'v2'],
}

# urls.py
urlpatterns = [
    path('api/v1/', include('apps.courses.urls')),
    path('api/v2/', include('apps.courses.urls_v2')),
]

# views.py
class CourseViewSet(viewsets.ModelViewSet):
    def get_serializer_class(self):
        if self.request.version == 'v2':
            return CourseV2Serializer
        return CourseSerializer
```

## Rate Limiting

### Throttling Configuration

```python
# settings/base.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    }
}

# Custom throttle
from rest_framework.throttling import UserRateThrottle


class UploadRateThrottle(UserRateThrottle):
    """Rate limit for video uploads."""
    rate = '10/day'


class VideoViewSet(viewsets.ModelViewSet):
    throttle_classes = [UploadRateThrottle]
```

## CORS Configuration

```python
# settings/base.py
INSTALLED_APPS += ['corsheaders']

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Before CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    ...
]

# Development
CORS_ALLOW_ALL_ORIGINS = True  # Only for development!

# Production
CORS_ALLOWED_ORIGINS = [
    'https://frontend.example.com',
    'https://www.example.com',
]

CORS_ALLOW_CREDENTIALS = True
```

## Checklist

Before deploying API endpoints:

- [ ] URLs follow REST conventions (plural nouns)
- [ ] HTTP methods used correctly
- [ ] Appropriate status codes returned
- [ ] Error responses include helpful messages
- [ ] Authentication required where needed
- [ ] Permissions properly enforced
- [ ] Filtering & pagination configured
- [ ] Rate limiting enabled for sensitive endpoints
- [ ] CORS configured for production domains
- [ ] API versioning strategy defined