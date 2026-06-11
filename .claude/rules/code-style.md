# Code Style Rules (PEP8 + Django Best Practices)

## Python (PEP8)

### Line Length & Formatting
- Max line length: **88 characters** (Black style, not 79)
- Indentation: **4 spaces** (no tabs)
- Blank lines: 2 before classes, 1 before methods
- Trailing commas: Always use in multi-line structures

### Imports Organization
```python
# Order: stdlib → third-party → local (separated by blank lines)
import json
import os
from datetime import datetime

from django.db import models
from rest_framework import serializers

from apps.users.models import User
from .utils import calculate_discount
```

### Naming Conventions

- Variables/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`
- Django-specific:
  - Models: Singular noun (`User`, not `Users`)
  - Apps: Plural noun (`users/`, `courses/`)

### Docstrings (Google Style)

```python
def calculate_total(items: list, discount: float = 0.0) -> float:
    """Calculate total price with optional discount.
    
    Args:
        items: List of items with price attribute
        discount: Discount percentage (0-100)
        
    Returns:
        Total price after discount
        
    Raises:
        ValueError: If discount is negative or > 100
        
    Example:
        >>> calculate_total([item1, item2], discount=10)
        90.0
    """
    if discount < 0 or discount > 100:
        raise ValueError("Discount must be between 0 and 100")
    
    subtotal = sum(item.price for item in items)
    return subtotal * (1 - discount / 100)
```

### Type Hints (Required)

```python
from typing import List, Optional, Dict, Any
from django.contrib.auth.models import User

def get_user_courses(
    user: User,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """Get courses for a user."""
    queryset = user.enrollments.all()
    if active_only:
        queryset = queryset.filter(active=True)
    return list(queryset.values())
```

## Django Conventions

### Models

```python
from django.db import models
from apps.core.models import TimeStampedModel


class Course(TimeStampedModel):
    """Course model with pricing and enrollment tracking.
    
    Attributes:
        name: Course title
        price: Course price (0 for free courses)
        instructor: Course creator
    """
    
    name = models.CharField(
        max_length=200,
        help_text="Course title"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Price in BRL (0 for free)"
    )
    instructor = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='courses_created'
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'
        indexes = [
            models.Index(fields=['instructor', '-created_at']),
        ]
    
    def __str__(self) -> str:
        return self.name
    
    def is_free(self) -> bool:
        """Check if course is free."""
        return self.price == 0
```

### Views (DRF)
```python
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Course
from .serializers import CourseSerializer, CourseDetailSerializer
from .permissions import IsCourseInstructor


class CourseViewSet(viewsets.ModelViewSet):
    """ViewSet for Course CRUD operations.
    
    Permissions:
        - List/Retrieve: Any user
        - Create: Authenticated users
        - Update/Delete: Course instructor only
    """
    
    queryset = Course.objects.select_related('instructor')
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    def get_permissions(self):
        """Granular permissions per action."""
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsCourseInstructor()]
        return super().get_permissions()
    
    @action(detail=True, methods=['post'])
    def enroll(self, request, pk=None):
        """Enroll current user in course."""
        course = self.get_object()
        # Implementation here
        return Response(
            {"detail": "Enrolled successfully"},
            status=status.HTTP_201_CREATED
        )
```

### Serializers
```python
from rest_framework import serializers
from .models import Course


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course list/create."""
    
    instructor_name = serializers.CharField(
        source='instructor.get_full_name',
        read_only=True
    )
    is_free = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id',
            'name',
            'price',
            'instructor',
            'instructor_name',
            'is_free',
            'created_at',
        ]
        read_only_fields = ['created_at']
    
    def validate_price(self, value):
        """Ensure price is non-negative."""
        if value < 0:
            raise serializers.ValidationError(
                "Price cannot be negative"
            )
        return value
```
## Common Violations & Fixes

### ❌ BAD

```python
# Line too long
def create_enrollment(course_id, user_id, payment_id, metadata_with_extra_details):
    pass

# Unused import
from django.db import models
import json  # Not used

# No docstring
def calculate(x, y):
    return x + y

# Inconsistent spacing
result=x+y
my_list = [1,2,3]
```

### ✅ GOOD

```python
# Proper line length
def create_enrollment(
    course_id: int,
    user_id: int,
    payment_id: str,
    metadata: dict
) -> Enrollment:
    """Create enrollment after payment confirmation."""
    pass

# Clean imports (only what's used)
from django.db import models

# With docstring
def calculate(x: float, y: float) -> float:
    """Add two numbers."""
    return x + y

# Proper spacing
result = x + y
my_list = [1, 2, 3]
```

## Validation Checklist

Before committing code, ensure:

- [ ] No lines exceed 88 characters
- [ ] All imports organized (stdlib → third-party → local)
- [ ] No unused imports (flake8 F401)
- [ ] All public methods have docstrings
- [ ] Type hints on all function signatures
- [ ] No `print()` statements (use logging)
- [ ] No bare `except:` clauses
- [ ] Strings use double quotes (except docstrings use triple double)
- [ ] No commented-out code blocks
- [ ] All Django queries optimized (select_related/prefetch_related)

## Tools

Run these before committing:

```bash
# Check violations
flake8 apps/

# Auto-fix formatting
black apps/

# Auto-fix imports
isort apps/

# Deep analysis
pylint apps/
```



