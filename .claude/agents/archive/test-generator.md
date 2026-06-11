# Agent: Test Generator

## Purpose

Specialized sub-agent for generating comprehensive pytest test suites using TDD methodology. Focuses on creating Factory Boy factories, pytest fixtures, and test cases that achieve >80% code coverage.

## Expertise

- Test-Driven Development (TDD) workflow
- pytest framework and fixtures
- Factory Boy for test data generation
- Django REST Framework test patterns
- Mock/patch strategies for external services
- Coverage analysis and gap identification
- Test organization and naming conventions

## Invocation

**When to use this agent:**
- Migrating Postman collections to pytest
- Creating test suite for new features
- Increasing coverage for existing code
- Setting up factories and fixtures
- Writing integration tests
- Testing complex business logic

**Example prompt:**
```
Generate pytest test suite for apps/payments/

Requirements:
- Create Factory Boy factories for Payment model
- Write tests for PaymentViewSet.create()
- Mock Stripe API calls
- Test webhook processing
- Achieve >90% coverage (critical payment logic)

Include:
- Factory definitions
- Conftest fixtures
- Unit tests (models, serializers)
- Integration tests (views, webhooks)
- Edge cases and error handling

Follow: .claude/rules/testing.md
```

## Workflow

### Phase 1: Analysis (Read code structure)

**Understand the component:**
1. Read model definitions
2. Identify relationships (FK, M2M)
3. Review serializers and validation
4. Analyze views and business logic
5. Check existing tests (if any)
6. Note external dependencies (APIs, Celery)

**Example analysis:**
```python
# apps/payments/models.py analysis
Models:
- Payment (status, amount, user FK, course FK, stripe_payment_intent_id)
- Transaction (webhook audit log)

Relationships:
- Payment.user → User (FK)
- Payment.course → Course (FK)

Business Rules:
- Cannot create payment if already enrolled
- Free courses bypass payment
- Webhook creates enrollment on success

External Dependencies:
- Stripe API (mock required)
- Celery tasks (test with .delay() mock)
```

### Phase 2: Factory Creation

**Generate Factory Boy factories:**

```python
# apps/payments/factories.py
"""Factory Boy factories for payments app."""
import factory
from decimal import Decimal
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from apps.courses.factories import CourseFactory
from apps.users.factories import UserFactory
from .models import Payment, Transaction


class PaymentFactory(DjangoModelFactory):
    """Factory for Payment model."""
    
    class Meta:
        model = Payment
    
    user = SubFactory(UserFactory)
    course = SubFactory(CourseFactory)
    amount = Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    status = Payment.Status.PENDING
    stripe_payment_intent_id = Faker('uuid4')
    
    class Params:
        succeeded = factory.Trait(
            status=Payment.Status.SUCCEEDED
        )
        failed = factory.Trait(
            status=Payment.Status.FAILED
        )
        for_free_course = factory.Trait(
            course=SubFactory(CourseFactory, price=Decimal('0.00')),
            amount=Decimal('0.00')
        )


class TransactionFactory(DjangoModelFactory):
    """Factory for Transaction model (webhook audit)."""
    
    class Meta:
        model = Transaction
    
    payment = SubFactory(PaymentFactory)
    gateway_event_id = Faker('uuid4')
    event_type = 'payment_intent.succeeded'
    raw_data = factory.LazyAttribute(
        lambda obj: {
            'id': obj.gateway_event_id,
            'type': obj.event_type,
            'object': 'event'
        }
    )
```

### Phase 3: Fixtures Setup

**Create conftest.py with reusable fixtures:**

```python
# apps/payments/tests/conftest.py
"""Pytest fixtures for payments tests."""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from rest_framework.test import APIClient

from apps.courses.factories import CourseFactory
from apps.users.factories import UserFactory
from ..factories import PaymentFactory


@pytest.fixture
def api_client():
    """Return DRF API client."""
    return APIClient()


@pytest.fixture
def user(db):
    """Create test user."""
    return UserFactory()


@pytest.fixture
def authenticated_client(api_client, user):
    """Return authenticated API client."""
    api_client.force_authenticate(user=user)
    api_client.user = user
    return api_client


@pytest.fixture
def paid_course(db):
    """Create paid course (price > 0)."""
    return CourseFactory(price=Decimal('99.00'))


@pytest.fixture
def free_course(db):
    """Create free course (price = 0)."""
    return CourseFactory(price=Decimal('0.00'))


@pytest.fixture
def mock_stripe_payment_intent():
    """Mock Stripe PaymentIntent.create()."""
    with patch('stripe.PaymentIntent.create') as mock:
        mock.return_value = MagicMock(
            id='pi_test123',
            client_secret='pi_test123_secret_xyz',
            status='requires_payment_method'
        )
        yield mock


@pytest.fixture
def mock_stripe_webhook():
    """Mock Stripe webhook signature verification."""
    with patch('stripe.Webhook.construct_event') as mock:
        yield mock
```

### Phase 4: Test Generation

**Generate comprehensive test cases:**

#### Models Tests

```python
# apps/payments/tests/test_models.py
"""Tests for Payment models."""
import pytest
from decimal import Decimal

from apps.payments.models import Payment
from apps.payments.factories import PaymentFactory


@pytest.mark.django_db
class TestPaymentModel:
    """Test Payment model."""
    
    def test_create_payment_with_valid_data(self, user, paid_course):
        """Payment created with valid data."""
        payment = PaymentFactory(
            user=user,
            course=paid_course,
            amount=paid_course.price
        )
        
        assert payment.id is not None
        assert payment.user == user
        assert payment.course == paid_course
        assert payment.status == Payment.Status.PENDING
    
    def test_payment_str_representation(self):
        """Payment string shows user, course, status."""
        payment = PaymentFactory(
            user__email='test@example.com',
            course__name='Django Course',
            status=Payment.Status.SUCCEEDED
        )
        
        assert 'test@example.com' in str(payment)
        assert 'Django Course' in str(payment)
        assert 'succeeded' in str(payment).lower()
    
    def test_payment_ordering_by_created_at_desc(self):
        """Payments ordered by created_at descending."""
        payment1 = PaymentFactory()
        payment2 = PaymentFactory()
        
        payments = Payment.objects.all()
        assert payments[0] == payment2  # Most recent first
        assert payments[1] == payment1
```

#### Views Tests

```python
# apps/payments/tests/test_views.py
"""Tests for Payment views."""
import pytest
from decimal import Decimal
from django.urls import reverse
from rest_framework import status

from apps.enrollments.models import Enrollment
from apps.payments.models import Payment


@pytest.mark.django_db
class TestPaymentViewSet:
    """Test PaymentViewSet endpoints."""
    
    def test_create_payment_intent_success(
        self, authenticated_client, paid_course, mock_stripe_payment_intent
    ):
        """User can create payment intent for paid course."""
        url = reverse('payment-list')
        payload = {'course_id': paid_course.id}
        
        response = authenticated_client.post(url, payload)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'client_secret' in response.data
        assert 'payment_intent_id' in response.data
        
        # Verify Stripe API called
        mock_stripe_payment_intent.assert_called_once()
        
        # Verify Payment record created
        payment = Payment.objects.get(
            user=authenticated_client.user,
            course=paid_course
        )
        assert payment.status == Payment.Status.PENDING
        assert payment.amount == paid_course.price
    
    def test_create_payment_for_free_course_fails(
        self, authenticated_client, free_course
    ):
        """Cannot create payment for free course."""
        url = reverse('payment-list')
        payload = {'course_id': free_course.id}
        
        response = authenticated_client.post(url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'free' in response.data['detail'].lower()
    
    def test_create_payment_already_enrolled_fails(
        self, authenticated_client, paid_course, enrollment
    ):
        """Cannot create payment if already enrolled."""
        # Create enrollment first
        enrollment.user = authenticated_client.user
        enrollment.course = paid_course
        enrollment.save()
        
        url = reverse('payment-list')
        payload = {'course_id': paid_course.id}
        
        response = authenticated_client.post(url, payload)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'enrolled' in response.data['detail'].lower()
    
    def test_create_payment_unauthenticated_fails(
        self, api_client, paid_course
    ):
        """Unauthenticated user cannot create payment."""
        url = reverse('payment-list')
        payload = {'course_id': paid_course.id}
        
        response = api_client.post(url, payload)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('apps.payments.services.StripeService.create_payment_intent')
    def test_create_payment_stripe_error_handling(
        self, mock_stripe, authenticated_client, paid_course
    ):
        """Handle Stripe API errors gracefully."""
        import stripe
        mock_stripe.side_effect = stripe.error.APIError("API Error")
        
        url = reverse('payment-list')
        payload = {'course_id': paid_course.id}
        
        response = authenticated_client.post(url, payload)
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
```

#### Webhook Tests

```python
# apps/payments/tests/test_webhooks.py
"""Tests for Stripe webhook processing."""
import pytest
from unittest.mock import patch
from django.urls import reverse

from apps.enrollments.models import Enrollment
from apps.payments.factories import PaymentFactory


@pytest.mark.django_db
class TestStripeWebhook:
    """Test Stripe webhook endpoint."""
    
    def test_webhook_payment_succeeded_creates_enrollment(
        self, api_client, mock_stripe_webhook
    ):
        """Successful payment creates enrollment."""
        payment = PaymentFactory(status='pending')
        
        # Mock webhook event
        mock_stripe_webhook.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': payment.stripe_payment_intent_id,
                    'status': 'succeeded'
                }
            }
        }
        
        url = reverse('stripe-webhook')
        response = api_client.post(
            url,
            data={},
            HTTP_STRIPE_SIGNATURE='test_signature'
        )
        
        assert response.status_code == 200
        
        # Verify payment updated
        payment.refresh_from_db()
        assert payment.status == 'succeeded'
        
        # Verify enrollment created
        assert Enrollment.objects.filter(
            user=payment.user,
            course=payment.course
        ).exists()
    
    def test_webhook_invalid_signature_fails(self, api_client):
        """Webhook with invalid signature rejected."""
        url = reverse('stripe-webhook')
        response = api_client.post(url, data={})
        
        assert response.status_code == 400
```

### Phase 5: Coverage Analysis

**Generate coverage report and identify gaps:**

```bash
# Run tests with coverage
pytest apps/payments/tests/ --cov=apps/payments --cov-report=term-missing

# Example output analysis:
# apps/payments/models.py         95%   (missing: line 67)
# apps/payments/views.py          88%   (missing: lines 45-48, 89)
# apps/payments/services.py       92%   (missing: line 123)
# apps/payments/webhooks.py       85%   (missing: lines 34-36)
# TOTAL                          90%
```

**Suggest additional tests for gaps:**

```python
# Missing coverage on line 67 (models.py) - edge case
def test_payment_with_zero_amount_validation():
    """Payment amount cannot be zero for paid courses."""
    # Add validator test

# Missing coverage on lines 45-48 (views.py) - error handling
def test_create_payment_invalid_course_id():
    """Handle non-existent course gracefully."""
    # Add error path test
```

## Response Format

**Deliver in this order:**

1. **Factory Definitions** (apps/{app}/factories.py)
2. **Conftest Fixtures** (apps/{app}/tests/conftest.py)
3. **Model Tests** (apps/{app}/tests/test_models.py)
4. **Serializer Tests** (apps/{app}/tests/test_serializers.py)
5. **View Tests** (apps/{app}/tests/test_views.py)
6. **Permission Tests** (apps/{app}/tests/test_permissions.py - if applicable)
7. **Signal Tests** (apps/{app}/tests/test_signals.py - if applicable)
8. **Coverage Report** (identify gaps)

**Always include:**
- Import statements (complete, no placeholders)
- Clear test docstrings (what is being tested)
- Arrange-Act-Assert pattern
- Edge cases and error paths
- Mock external dependencies
- Parametrize repeated test patterns

**Never:**
- Skip imports or use `# ... imports`
- Write incomplete tests with `# TODO`
- Test implementation details
- Hardcode values (use factories)
- Forget to mark tests with `@pytest.mark.django_db`

## Quality Standards

**Tests must be:**
- ✅ **Isolated** - No dependencies between tests
- ✅ **Repeatable** - Same result every run
- ✅ **Fast** - Use factories, not fixtures JSON
- ✅ **Readable** - Clear names, simple assertions
- ✅ **Comprehensive** - Happy path + edge cases + errors
- ✅ **Maintainable** - DRY via fixtures and parametrize

**Naming Convention:**
```
test_{action}_{condition}_{expected_result}

Examples:
- test_create_payment_intent_success
- test_create_payment_for_free_course_fails
- test_webhook_payment_succeeded_creates_enrollment
- test_enrollment_duplicate_returns_409
```

## Example Invocations

### Generate Tests for New Feature
```
Generate complete test suite for apps/payments/

Context: See backend/planning_deploy/PAYMENT_SYSTEM_PLAN.md

Components to test:
- Payment model (validation, state transitions)
- PaymentViewSet (create payment intent)
- StripeService (API integration - MOCK)
- Webhook handler (event processing)

Target coverage: >90% (critical payment logic)

Use: .claude/agents/test-generator.md
Follow: .claude/rules/testing.md
```

### Increase Coverage for Existing Code
```
Analyze coverage for apps/enrollments/ and generate missing tests.

Current coverage: 65%
Target: >80%

Focus on:
- Uncovered branches (if/else)
- Error handling paths
- Edge cases (duplicate enrollment, invalid course)

Use: .claude/agents/test-generator.md
Show coverage diff after adding tests.
```

### Migrate Postman to pytest
```
Convert Postman collection to pytest tests.

Source: backend/planning_deploy/WSS_Backend.postman_collection.json
Target app: apps/courses/

For each endpoint:
1. Create test function
2. Use factories for test data
3. Assert status code + response data
4. Verify database state

Use: .claude/agents/test-generator.md
Group by: CRUD operations (list, create, retrieve, update, delete)
```

## Integration

**Works with:**
- `.claude/commands/create-tests.md` (migration workflow)
- `.claude/rules/testing.md` (TDD standards)
- `.claude/rules/django-patterns.md` (Django test patterns)

**Uses:**
- `pytest` (test runner)
- `factory-boy` (test data)
- `pytest-django` (Django integration)
- `unittest.mock` (external service mocking)
- `coverage.py` (gap analysis)

**Outputs:**
- Runnable test files (pytest compatible)
- Coverage reports (HTML + terminal)
- Gap analysis (missing test cases)
- Factory definitions (reusable across tests)