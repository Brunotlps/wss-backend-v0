# Command: Implement Feature (TDD)

## Objective

Implement new features using Test-Driven Development methodology: RED → GREEN → REFACTOR.

**Dependencies:**
- See: [.claude/rules/code-style.md](.claude/rules/code-style.md) (PEP8 conventions)
- See: [.claude/rules/testing.md](.claude/rules/testing.md) (Test patterns)
- See: [.claude/rules/django-patterns.md](.claude/rules/django-patterns.md) (Django best practices)

## Prerequisites

- [ ] Feature specification clear (acceptance criteria)
- [ ] Tests environment ready (pytest + factories)
- [ ] Git working tree clean
- [ ] PEP8 compliance tools configured

## TDD Workflow

### Phase 1: RED (Write Failing Test)

**Step 1: Understand Requirements**

Example Feature: **Payment System Integration**

```markdown
## Feature: Stripe Payment Processing

**As a** student
**I want to** pay for paid courses securely
**So that** I can enroll and access premium content

**Acceptance Criteria:**
1. ✅ User can initiate payment for paid course
2. ✅ Payment processed via Stripe Payment Intent
3. ✅ Webhook confirms payment success
4. ✅ Enrollment created only after payment confirmation
5. ✅ Cannot enroll in paid course without payment
6. ✅ Can enroll in free courses directly
7. ✅ Payment status tracked (pending, succeeded, failed)
```

**Step 2: Write Test First**

```python
# apps/payments/tests/test_views.py
import pytest
from django.urls import reverse
from rest_framework import status
from apps.payments.models import Payment


@pytest.mark.django_db
def test_create_payment_intent_for_course(authenticated_user, paid_course):
    """User can create payment intent for paid course."""
    # Arrange
    url = reverse('payment-create')
    payload = {
        "course_id": paid_course.id,
        "amount": str(paid_course.price)
    }
    
    # Act
    response = authenticated_user.post(url, payload, format='json')
    
    # Assert
    assert response.status_code == status.HTTP_201_CREATED
    assert 'client_secret' in response.data
    assert 'payment_intent_id' in response.data
    
    # Verify Payment record created
    payment = Payment.objects.get(
        user=authenticated_user.user,
        course=paid_course
    )
    assert payment.status == Payment.Status.PENDING
    assert payment.amount == paid_course.price
```

**Step 3: Run Test (Should FAIL)**

```bash
pytest apps/payments/tests/test_views.py::test_create_payment_intent_for_course -v

# Expected output:
# FAILED - AttributeError: 'NoneType' object has no attribute 'price'
# or
# FAILED - No route found for 'payment-create'
```

**Claude Code Instructions:**

```
Task: Implement Payment Intent creation endpoint

Context: 
- Test written in apps/payments/tests/test_views.py
- Test currently FAILING (expected)
- See .claude/context/tasks/task-5-payment.md for architecture

Requirements:
1. Create Payment model (status, amount, user, course, stripe_payment_intent_id)
2. Create PaymentSerializer
3. Create PaymentViewSet with 'create' action
4. Integrate StripeService.create_payment_intent()
5. Add URL route

Rules:
- Follow .claude/rules/django-patterns.md
- Minimal code to pass test
- NO over-engineering
- ASK before each file creation

Start with: apps/payments/models.py
```

### Phase 2: GREEN (Make Test Pass)

**Step 1: Implement Minimal Code**

```python
# apps/payments/models.py
from django.db import models
from apps.core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """Payment record for course purchases."""
    
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCEEDED = 'succeeded', 'Succeeded'
        FAILED = 'failed', 'Failed'
        CANCELLED = 'cancelled', 'Cancelled'
    
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.user.email} - {self.course.name} - {self.status}"
```

```python
# apps/payments/services.py
import stripe
from django.conf import settings
from .models import Payment

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service layer for Stripe operations."""
    
    @staticmethod
    def create_payment_intent(user, course) -> dict:
        """Create Stripe Payment Intent.
        
        Args:
            user: User making the payment
            course: Course being purchased
        
        Returns:
            dict with 'client_secret' and 'payment_intent_id'
        """
        # Create Payment Intent in Stripe
        intent = stripe.PaymentIntent.create(
            amount=int(course.price * 100),  # Convert to cents
            currency='brl',
            metadata={
                'user_id': user.id,
                'course_id': course.id,
            }
        )
        
        # Create Payment record
        payment = Payment.objects.create(
            user=user,
            course=course,
            amount=course.price,
            status=Payment.Status.PENDING,
            stripe_payment_intent_id=intent.id
        )
        
        return {
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'payment_id': payment.id
        }
```

```python
# apps/payments/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.courses.models import Course
from .services import StripeService


class PaymentViewSet(viewsets.GenericViewSet):
    """Payment operations."""
    
    permission_classes = [IsAuthenticated]
    
    def create(self, request):
        """Create payment intent for course."""
        course_id = request.data.get('course_id')
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"detail": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if course.price == 0:
            return Response(
                {"detail": "Course is free"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create payment intent
        result = StripeService.create_payment_intent(
            user=request.user,
            course=course
        )
        
        return Response(result, status=status.HTTP_201_CREATED)
```

**Step 2: Run Test Again (Should PASS)**

```bash
pytest apps/payments/tests/test_views.py::test_create_payment_intent_for_course -v

# Expected output:
# PASSED ✅
```

**Step 3: Verify All Tests Still Pass**

```bash
pytest apps/payments/tests/ -v
pytest --cov=apps/payments --cov-report=term
```

### Phase 3: REFACTOR (Improve Code)

**Step 1: Identify Improvements**

```python
# Code smells to fix:
1. Missing error handling (Stripe API failure)
2. No transaction atomicity
3. Hardcoded currency
4. Missing type hints
5. No docstrings
6. Duplicate enrollment check missing
```

**Step 2: Refactor with Tests Passing**

```python
# apps/payments/services.py (REFACTORED)
import stripe
import logging
from django.conf import settings
from django.db import transaction
from typing import Dict, Optional
from .models import Payment
from apps.enrollments.models import Enrollment

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Custom exception for payment processing errors."""
    pass


class StripeService:
    """Service layer for Stripe payment operations."""
    
    DEFAULT_CURRENCY = 'brl'
    
    @staticmethod
    @transaction.atomic
    def create_payment_intent(user, course) -> Dict[str, any]:
        """Create Stripe Payment Intent for course purchase.
        
        Args:
            user: User instance making the payment.
            course: Course instance being purchased.
        
        Returns:
            Dictionary containing:
                - client_secret: Stripe client secret for frontend
                - payment_intent_id: Stripe Payment Intent ID
                - payment_id: Internal Payment record ID
        
        Raises:
            PaymentError: If Stripe API call fails.
            ValueError: If user already enrolled or course is free.
        """
        # Validate not already enrolled
        if Enrollment.objects.filter(user=user, course=course).exists():
            raise ValueError("User already enrolled in this course")
        
        # Validate course is paid
        if course.price <= 0:
            raise ValueError("Cannot create payment for free course")
        
        try:
            # Create Payment Intent in Stripe
            intent = stripe.PaymentIntent.create(
                amount=int(course.price * 100),  # Convert to cents
                currency=StripeService.DEFAULT_CURRENCY,
                metadata={
                    'user_id': user.id,
                    'user_email': user.email,
                    'course_id': course.id,
                    'course_name': course.name,
                },
                automatic_payment_methods={'enabled': True},
            )
            
            logger.info(
                f"Payment Intent created: {intent.id} "
                f"for user {user.email}, course {course.name}"
            )
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe API error: {str(e)}")
            raise PaymentError(f"Payment processing failed: {str(e)}")
        
        # Create Payment record
        payment = Payment.objects.create(
            user=user,
            course=course,
            amount=course.price,
            status=Payment.Status.PENDING,
            stripe_payment_intent_id=intent.id
        )
        
        return {
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'payment_id': payment.id,
        }
```

**Step 3: Run Tests Again (Should Still PASS)**

```bash
pytest apps/payments/tests/ -v

# All tests should pass after refactoring
```

**Step 4: Check Code Quality**

```bash
# PEP8 compliance
flake8 apps/payments/

# Format code
black apps/payments/
isort apps/payments/

# Type checking (optional)
mypy apps/payments/

# Coverage
pytest apps/payments/tests/ --cov=apps/payments --cov-report=term
# Target: >90% for critical payment logic
```

### Phase 4: Add Edge Cases

**Write Additional Tests:**

```python
def test_create_payment_already_enrolled_fails(authenticated_user, paid_course, enrollment):
    """Cannot create payment if already enrolled."""
    url = reverse('payment-create')
    payload = {"course_id": paid_course.id}
    
    response = authenticated_user.post(url, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already enrolled" in response.data['detail'].lower()


def test_create_payment_for_free_course_fails(authenticated_user, free_course):
    """Cannot create payment for free course."""
    url = reverse('payment-create')
    payload = {"course_id": free_course.id}
    
    response = authenticated_user.post(url, payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@patch('stripe.PaymentIntent.create')
def test_create_payment_stripe_api_error(mock_stripe, authenticated_user, paid_course):
    """Handle Stripe API errors gracefully."""
    mock_stripe.side_effect = stripe.error.APIError("API Error")
    
    url = reverse('payment-create')
    payload = {"course_id": paid_course.id}
    
    response = authenticated_user.post(url, payload)
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
```

### Phase 5: Commit

**Create Logical Commit:**

```bash
git add apps/payments/
git commit -m "feat(payments): implement Stripe payment intent creation

Implementation includes:
- Payment model with status tracking
- StripeService for Stripe API integration
- PaymentViewSet with create action
- Transaction atomicity for payment creation
- Error handling for Stripe API failures
- Validation (duplicate enrollment, free courses)

Business rules:
- Cannot enroll in paid course without payment
- Cannot create payment if already enrolled
- Free courses bypass payment flow

Tests:
- test_create_payment_intent_for_course ✅
- test_create_payment_already_enrolled_fails ✅
- test_create_payment_for_free_course_fails ✅
- test_create_payment_stripe_api_error ✅

Coverage: 95% (38/40 lines)

Refs: PAYMENT_SYSTEM_PLAN.md, Sprint 8 Task 5"
```

## Feature Implementation Checklist

Before marking feature complete:

- [ ] **RED:** Failing tests written first
- [ ] **GREEN:** Tests pass with minimal implementation
- [ ] **REFACTOR:** Code improved while tests pass
- [ ] **Edge Cases:** Error paths tested
- [ ] **Documentation:** Docstrings added (Google style)
- [ ] **Type Hints:** Function signatures typed
- [ ] **PEP8:** Code formatted (black + isort)
- [ ] **Coverage:** >80% overall, >90% critical paths
- [ ] **Security:** Input validation, error handling
- [ ] **Commit:** Conventional message with context

## Common TDD Mistakes

### ❌ Writing Code Before Tests

```python
# WRONG ORDER:
1. Write model ❌
2. Write view ❌
3. Write tests ❌
```

### ✅ Correct TDD Order

```python
# RIGHT ORDER:
1. Write failing test ✅
2. Run test (RED) ✅
3. Write minimal code ✅
4. Run test (GREEN) ✅
5. Refactor ✅
6. Run test (still GREEN) ✅
```

### ❌ Testing Implementation Details

```python
# BAD: Testing internal method
def test_calculate_price_calls_discount_method():
    course.calculate_price()
    assert course._apply_discount.called  # ❌ Implementation detail
```

### ✅ Testing Behavior

```python
# GOOD: Testing outcome
def test_calculate_price_with_discount():
    course = CourseFactory(price=100, discount=0.1)
    assert course.calculate_price() == 90.0  # ✅ Behavior
```

## Time Estimates

**Small Feature (1-2 files):** 2-4 hours
- RED: 30 min
- GREEN: 1-2h
- REFACTOR: 30-60 min
- Edge cases: 30 min

**Medium Feature (3-5 files):** 4-8 hours
**Large Feature (6+ files, like payments):** 1-3 days

## Success Criteria

```
✅ Feature Implementation Complete!

Feature: {FEATURE_NAME}

TDD Phases:
- RED: X failing tests written
- GREEN: All tests passing
- REFACTOR: Code quality improved

Code Quality:
- PEP8 compliant (flake8: 0 errors)
- Formatted (black + isort)
- Documented (docstrings + type hints)
- Secure (input validation, error handling)

Test Coverage: X% (X/X lines)
Commits: X (conventional messages)

Ready for: Code review / Production deployment
```