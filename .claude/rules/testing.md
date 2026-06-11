# Testing Rules (TDD Style)

## Framework & Tools

- **Test Runner:** pytest + pytest-django
- **Fixtures:** factory-boy for test data
- **Coverage:** pytest-cov (target: >80%)
- **Mocking:** unittest.mock + pytest-mock

## TDD Workflow (RED → GREEN → REFACTOR)

### Phase 1: RED (Write Failing Test)

```python
# apps/payments/tests/test_services.py
import pytest
from apps.payments.services import StripeService


@pytest.mark.django_db
def test_create_payment_intent_with_valid_data_returns_client_secret():
    """Test payment intent creation returns client secret."""
    # Arrange
    service = StripeService()
    course = CourseFactory(price=100.00)
    user = UserFactory()
    
    # Act
    result = service.create_payment_intent(
        user=user,
        course=course
    )
    
    # Assert
    assert 'client_secret' in result
    assert result['amount'] == 10000  # cents

# Run: pytest -v
# Expected: FAILED (StripeService doesn't exist yet)
```

### Phase 2: GREEN (Minimal Implementation)

```python
# apps/payments/services.py
class StripeService:
    """Service for Stripe payment operations."""
    
    def create_payment_intent(self, user, course):
        """Create Stripe payment intent."""
        import stripe
        
        intent = stripe.PaymentIntent.create(
            amount=int(course.price * 100),
            currency='brl',
            metadata={'user_id': user.id, 'course_id': course.id}
        )
        
        return {
            'client_secret': intent.client_secret,
            'amount': intent.amount
        }

# Run: pytest -v
# Expected: PASSED
```

### Phase 3: REFACTOR (Improve Quality)

```python
# Refactor: Add error handling, logging, type hints
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class StripeService:
    """Service for Stripe payment operations."""
    
    def create_payment_intent(
        self,
        user: 'User',
        course: 'Course'
    ) -> Dict[str, Any]:
        """Create Stripe payment intent.
        
        Args:
            user: User making the payment
            course: Course being purchased
            
        Returns:
            Dict with client_secret and amount
            
        Raises:
            StripeError: If payment intent creation fails
        """
        import stripe
        
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(course.price * 100),
                currency='brl',
                metadata={
                    'user_id': user.id,
                    'course_id': course.id
                }
            )
            
            logger.info(
                f"Payment intent created: {intent.id} "
                f"for user {user.id}, course {course.id}"
            )
            
            return {
                'client_secret': intent.client_secret,
                'amount': intent.amount
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            raise

# Run: pytest -v
# Expected: Still PASSED (refactoring didn't break anything)
```

## Test Structure

```
apps/<app_name>/tests/
├── __init__.py
├── factories.py              # Factory Boy fixtures
├── conftest.py               # Pytest fixtures
├── test_models.py            # Model tests
├── test_views.py             # View/API tests
├── test_serializers.py       # Serializer validation tests
├── test_permissions.py       # Permission logic tests
├── test_services.py          # Business logic tests
└── test_integration.py       # End-to-end flows
```

## Naming Convention

```python
def test_<action>_<condition>_<expected_result>():
    """Test that <action> with <condition> produces <expected>."""
    # Test implementation
```

**Examples:**
- `test_create_enrollment_with_paid_course_without_payment_returns_402`
- `test_list_certificates_unauthenticated_returns_401`
- `test_complete_enrollment_creates_certificate`

## Test Anatomy (Arrange-Act-Assert)

```python
@pytest.mark.django_db
def test_enrollment_completion_triggers_certificate_generation():
    """Test that completing enrollment creates certificate."""
    # Arrange: Setup test data
    user = UserFactory()
    course = CourseFactory()
    enrollment = EnrollmentFactory(
        user=user,
        course=course,
        completed=False
    )
    
    # Act: Perform action
    enrollment.completed = True
    enrollment.save()
    
    # Assert: Verify outcome
    assert Certificate.objects.filter(
        enrollment=enrollment
    ).exists()
    certificate = Certificate.objects.get(enrollment=enrollment)
    assert certificate.code is not None
    assert len(certificate.code) == 12
```

## Factory Boy Patterns

```python
# apps/users/tests/factories.py
import factory
from factory.django import DjangoModelFactory
from apps.users.models import User


class UserFactory(DjangoModelFactory):
    """Factory for User model."""
    
    class Meta:
        model = User
    
    email = factory.Sequence(lambda n: f'user{n}@test.com')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    
    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        """Set password after user creation."""
        if create:
            obj.set_password(extracted or 'testpass123')
            obj.save()


class InstructorFactory(UserFactory):
    """Factory for instructor users."""
    
    is_instructor = True


# Usage in tests
def test_user_creation():
    user = UserFactory()
    assert user.email.endswith('@test.com')
    
    user_with_password = UserFactory(password='custom123')
    assert user_with_password.check_password('custom123')
    
    instructor = InstructorFactory()
    assert instructor.is_instructor is True
```

## Pytest Fixtures (conftest.py)

```python
# apps/conftest.py (shared across all apps)
import pytest
from rest_framework.test import APIClient
from .users.tests.factories import UserFactory


@pytest.fixture
def api_client():
    """Return DRF API client."""
    return APIClient()


@pytest.fixture
def authenticated_user(api_client):
    """Return authenticated user with client."""
    user = UserFactory()
    api_client.force_authenticate(user=user)
    return user


@pytest.fixture
def instructor_user(api_client):
    """Return authenticated instructor."""
    from .users.tests.factories import InstructorFactory
    instructor = InstructorFactory()
    api_client.force_authenticate(instructor)
    return instructor


# Usage in tests
def test_list_courses_authenticated(api_client, authenticated_user):
    """Test authenticated user can list courses."""
    response = api_client.get('/api/courses/')
    assert response.status_code == 200
```

## Testing Patterns

### Model Tests

```python
@pytest.mark.django_db
class TestCourseModel:
    """Test suite for Course model."""
    
    def test_is_free_with_zero_price_returns_true(self):
        """Test is_free() returns True for free courses."""
        course = CourseFactory(price=0)
        assert course.is_free() is True
    
    def test_is_free_with_positive_price_returns_false(self):
        """Test is_free() returns False for paid courses."""
        course = CourseFactory(price=99.90)
        assert course.is_free() is False
    
    def test_str_returns_course_name(self):
        """Test __str__ returns course name."""
        course = CourseFactory(name="Django Mastery")
        assert str(course) == "Django Mastery"
```

### API Tests

```python
@pytest.mark.django_db
class TestCourseAPI:
    """Test suite for Course API endpoints."""
    
    def test_list_courses_returns_200(self, api_client):
        """Test GET /api/courses/ returns 200."""
        CourseFactory.create_batch(3)
        response = api_client.get('/api/courses/')
        
        assert response.status_code == 200
        assert len(response.data) == 3
    
    def test_create_course_unauthenticated_returns_401(self, api_client):
        """Test creating course without auth returns 401."""
        payload = {'name': 'New Course', 'price': 100}
        response = api_client.post('/api/courses/', payload)
        
        assert response.status_code == 401
    
    def test_create_course_authenticated_returns_201(
        self,
        api_client,
        authenticated_user
    ):
        """Test authenticated user can create course."""
        payload = {
            'name': 'New Course',
            'price': 100.00,
            'instructor': authenticated_user.id
        }
        response = api_client.post('/api/courses/', payload, format='json')
        
        assert response.status_code == 201
        assert response.data['name'] == 'New Course'
        assert Course.objects.filter(name='New Course').exists()
```

### Permission Tests

```python
@pytest.mark.django_db
class TestIsEnrolledPermission:
    """Test suite for IsEnrolled permission."""
    
    def test_has_permission_with_enrollment_returns_true(
        self,
        api_client,
        authenticated_user
    ):
        """Test enrolled user has permission."""
        course = CourseFactory()
        EnrollmentFactory(user=authenticated_user, course=course)
        video = VideoFactory(course=course)
        
        response = api_client.get(f'/api/videos/{video.id}/')
        
        assert response.status_code == 200
    
    def test_has_permission_without_enrollment_returns_403(
        self,
        api_client,
        authenticated_user
    ):
        """Test non-enrolled user gets 403."""
        course = CourseFactory()
        video = VideoFactory(course=course, order=2)  # Not free preview
        
        response = api_client.get(f'/api/videos/{video.id}/')
        
        assert response.status_code == 403
```

## Coverage Requirements

### Targets

- **Overall:** >80%
- **Critical paths:** >90% (payments, enrollments, permissions)
- **Models:** >85%
- **Views:** >80%
- **Utils:** >90%

### Running Coverage

```bash
# All tests with coverage
pytest --cov=apps --cov-report=html --cov-report=term-missing

# Specific app
pytest apps/payments/ --cov=apps.payments --cov-report=term

# Fail if below threshold
pytest --cov=apps --cov-fail-under=80
```

### Coverage Report

```
----------- coverage: platform linux, python 3.12 -----------
Name                              Stmts   Miss  Cover   Missing
---------------------------------------------------------------
apps/payments/models.py              50      5    90%   45-47, 89
apps/payments/services.py           100     10    90%   234-245
apps/payments/views.py               80     20    75%   56-78
---------------------------------------------------------------
TOTAL                               230     35    85%
```

## Mocking External Services

```python
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
@patch('stripe.PaymentIntent.create')
def test_create_payment_intent_calls_stripe_api(mock_create):
    """Test payment intent creation calls Stripe."""
    # Arrange
    mock_create.return_value = MagicMock(
        client_secret='pi_test_secret',
        amount=10000
    )
    service = StripeService()
    user = UserFactory()
    course = CourseFactory(price=100.00)
    
    # Act
    result = service.create_payment_intent(user, course)
    
    # Assert
    mock_create.assert_called_once_with(
        amount=10000,
        currency='brl',
        metadata={'user_id': user.id, 'course_id': course.id}
    )
    assert result['client_secret'] == 'pi_test_secret'
```

## Test Checklist

Before marking a feature complete:

- [ ] All happy paths tested
- [ ] All error cases tested (4xx, 5xx)
- [ ] Permissions tested (allow + deny)
- [ ] Edge cases covered (null, empty, invalid)
- [ ] Integration tests for full flows
- [ ] Coverage >80% for new code
- [ ] All tests pass locally
- [ ] No test warnings or deprecations
