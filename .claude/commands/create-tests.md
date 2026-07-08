# Command: Create Automated Tests

## Objective

Migrate Postman collection to pytest test suite, achieving >80% code coverage with TDD methodology.

**Dependencies:**
- See: [.claude/rules/code-style.md](.claude/rules/code-style.md) (PEP8 conventions)
- See: [.claude/rules/testing.md](.claude/rules/testing.md) (Test patterns)
- See: [.claude/rules/django-patterns.md](.claude/rules/django-patterns.md) (Django best practices)

## Prerequisites

- [ ] PEP8 validation complete
- [ ] Postman collection exported (WSS_Backend.postman_collection.json)
- [ ] pytest + factory-boy configured
- [ ] Test database accessible
- [ ] Git working tree clean

## Workflow

### Phase 1: Export Postman Collection (10 min)

**Export Steps:**

1. Open Postman Desktop
2. Select "WSS Backend" collection
3. Click ⋯ (three dots) → Export
4. Choose "Collection v2.1"
5. Save as: `backend/planning_deploy/WSS_Backend.postman_collection.json`
6. Verify export:
   ```bash
   cat backend/planning_deploy/WSS_Backend.postman_collection.json | jq '.info.name'
   # Should output: "WSS Backend"
   ```

**Analyze Collection:**

```bash
# Count total requests
cat backend/planning_deploy/WSS_Backend.postman_collection.json | jq '[.. | .request? | select(. != null)] | length'

# List all endpoints
cat backend/planning_deploy/WSS_Backend.postman_collection.json | jq -r '.. | .request?.url?.raw? | select(. != null)'

# Group by app
cat backend/planning_deploy/WSS_Backend.postman_collection.json | jq -r '.. | .request?.url?.raw? | select(. != null)' | grep -oE '/api/[^/]+' | sort | uniq -c
```

### Phase 2: Setup Test Infrastructure (30 min)

**Create Factories (apps/{app}/factories.py):**

```bash
# Generate factory skeleton for each app
for app in users courses videos enrollments certificates; do
  cat > backend/apps/$app/factories.py << EOF
"""Factory Boy factories for $app app."""
import factory
from factory import Faker, SubFactory
from factory.django import DjangoModelFactory

from .models import *


# TODO: Implement factories based on models
EOF
done
```

**Claude Code Instructions:**

```
Task: Create Factory Boy factories for app: {APP_NAME}

Reference:
- .claude/rules/testing.md (Factory patterns)
- apps/{APP_NAME}/models.py (model structure)

Requirements:
1. One factory per model
2. Use Faker for realistic data
3. SubFactory for ForeignKey relationships
4. Use Trait for variants (active/inactive, free/paid, etc.)
5. Include @factory.post_generation for M2M

Example Pattern:
```python
class CourseFactory(DjangoModelFactory):
    class Meta:
        model = Course
    
    name = Faker('sentence', nb_words=4)
    slug = Faker('slug')
    description = Faker('paragraph')
    price = Faker('pydecimal', left_digits=3, right_digits=2, positive=True)
    instructor = SubFactory('apps.users.factories.InstructorFactory')
    
    class Params:
        free = Trait(price=0)
        premium = Trait(price=Faker('pydecimal', min_value=50, max_value=200))
```

Start with: apps/users/factories.py
```

### Phase 3: Migrate Tests by App (2-3 days)

**Apps Priority Order:**
1. `users/` - Authentication foundation (4-6h)
2. `courses/` - Core domain logic (6-8h)
3. `enrollments/` - Business rules (4-6h)
4. `videos/` - File handling (3-4h)
5. `certificates/` - PDF generation (2-3h)

**Test Structure Per App:**

```
apps/{app}/
├── factories.py          # Factory Boy factories
├── tests/
│   ├── __init__.py
│   ├── conftest.py       # Pytest fixtures
│   ├── test_models.py    # Model validation & methods
│   ├── test_views.py     # API endpoints (from Postman)
│   ├── test_serializers.py  # Serialization logic
│   ├── test_permissions.py  # Permission classes
│   └── test_signals.py   # Signal handlers (if exists)
```

**Postman → pytest Migration Pattern:**

```python
# Postman Request:
# POST /api/auth/register/
# Body: {"email": "test@example.com", "password": "Pass123!", "name": "Test"}
# Expected: 201 Created

# pytest Test:
def test_user_registration_success(api_client):
    """Test successful user registration."""
    # Arrange
    payload = {
        "email": "test@example.com",
        "password": "Pass123!",
        "name": "Test User"
    }
    
    # Act
    response = api_client.post('/api/auth/register/', payload)
    
    # Assert
    assert response.status_code == 201
    assert response.data['email'] == payload['email']
    assert 'password' not in response.data  # Never expose password
    assert User.objects.filter(email=payload['email']).exists()
```

**TDD Workflow for Each Endpoint:**

```
1. RED: Write failing test from Postman request
2. Run: pytest apps/{app}/tests/test_views.py::test_name -v
3. GREEN: Implement minimal code (if not exists)
4. Run: pytest again → should pass
5. REFACTOR: Improve code quality
6. Run: pytest + coverage check
7. Commit: git commit -m "test({app}): add {endpoint} tests"
```

### Phase 4: Test Each App (Detailed)

#### 4.1 Users App (4-6h)

**Endpoints to Test:**
- `POST /api/auth/register/` - Registration
- `POST /api/auth/login/` - JWT token obtain
- `POST /api/auth/refresh/` - Token refresh
- `GET /api/users/me/` - Current user profile
- `PATCH /api/users/me/` - Update profile

**Test Files:**

```bash
# apps/users/tests/test_models.py
- test_user_creation_with_valid_data
- test_user_email_normalization
- test_user_str_representation
- test_instructor_profile_creation

# apps/users/tests/test_views.py
- test_register_user_success
- test_register_duplicate_email_fails
- test_login_valid_credentials
- test_login_invalid_credentials
- test_token_refresh_success
- test_get_current_user_authenticated
- test_get_current_user_unauthenticated
- test_update_profile_success

# apps/users/tests/test_serializers.py
- test_user_serializer_excludes_password
- test_registration_serializer_validates_email
- test_registration_serializer_hashes_password
```

**Run & Verify:**

```bash
pytest apps/users/tests/ -v --cov=apps/users --cov-report=term
# Target: >90% coverage for users (critical auth logic)
```

#### 4.2 Courses App (6-8h)

**Endpoints to Test:**
- `GET /api/courses/` - List courses
- `POST /api/courses/` - Create course (instructor only)
- `GET /api/courses/{id}/` - Course detail
- `PATCH /api/courses/{id}/` - Update course (instructor only)
- `DELETE /api/courses/{id}/` - Delete course (instructor only)
- `GET /api/courses/?search=django` - Search
- `GET /api/courses/?price_min=0&price_max=100` - Filtering

**Key Tests:**

```python
# test_views.py
def test_create_course_as_instructor(authenticated_instructor):
    """Instructor can create course."""
    payload = {
        "name": "Django Course",
        "description": "Learn Django",
        "price": "99.00"
    }
    response = authenticated_instructor.post('/api/courses/', payload)
    assert response.status_code == 201
    assert response.data['instructor'] == authenticated_instructor.user.id

def test_create_course_as_student_fails(authenticated_user):
    """Regular user cannot create course."""
    payload = {"name": "Course", "price": "50.00"}
    response = authenticated_user.post('/api/courses/', payload)
    assert response.status_code == 403

def test_update_course_only_by_instructor(course, authenticated_instructor, authenticated_user):
    """Only course instructor can update."""
    url = f'/api/courses/{course.id}/'
    payload = {"name": "Updated Name"}
    
    # Owner can update
    response = authenticated_instructor.patch(url, payload)
    assert response.status_code == 200
    
    # Other user cannot
    response = authenticated_user.patch(url, payload)
    assert response.status_code == 403
```

**Run & Verify:**

```bash
pytest apps/courses/tests/ -v --cov=apps/courses --cov-report=term
# Target: >85% coverage
```

#### 4.3 Enrollments App (4-6h)

**Critical Business Rule Tests:**

```python
def test_cannot_enroll_in_paid_course_without_payment(user, paid_course):
    """User cannot enroll in paid course without valid payment."""
    response = authenticated_user.post(
        f'/api/courses/{paid_course.id}/enroll/'
    )
    assert response.status_code == 402  # Payment Required
    assert not Enrollment.objects.filter(
        user=user,
        course=paid_course
    ).exists()

def test_can_enroll_in_free_course(user, free_course):
    """User can directly enroll in free course."""
    response = authenticated_user.post(
        f'/api/courses/{free_course.id}/enroll/'
    )
    assert response.status_code == 201

def test_cannot_enroll_twice_in_same_course(user, course, enrollment):
    """Prevent duplicate enrollment."""
    response = authenticated_user.post(
        f'/api/courses/{course.id}/enroll/'
    )
    assert response.status_code == 409  # Conflict
```

#### 4.4 Videos App (3-4h)

**File Upload Tests:**

```python
def test_upload_valid_video_file(authenticated_instructor, course):
    """Upload valid MP4 video."""
    video_file = SimpleUploadedFile(
        "test_video.mp4",
        b"fake video content",
        content_type="video/mp4"
    )
    payload = {
        "title": "Introduction",
        "file": video_file,
        "course": course.id
    }
    response = authenticated_instructor.post('/api/videos/', payload)
    assert response.status_code == 201

def test_upload_invalid_mime_type_fails(authenticated_instructor, course):
    """Reject non-video files."""
    text_file = SimpleUploadedFile(
        "fake_video.mp4",  # .mp4 extension
        b"This is not a video",
        content_type="text/plain"  # Wrong MIME
    )
    payload = {"title": "Video", "file": text_file, "course": course.id}
    response = authenticated_instructor.post('/api/videos/', payload)
    assert response.status_code == 400
```

#### 4.5 Certificates App (2-3h)

**Signal & Task Tests:**

```python
def test_certificate_created_on_enrollment_completion(enrollment):
    """Certificate generated when enrollment completed."""
    enrollment.completed = True
    enrollment.save()
    
    # Check certificate created
    assert Certificate.objects.filter(enrollment=enrollment).exists()

@patch('apps.certificates.tasks.generate_pdf')
def test_certificate_pdf_generation_async(mock_generate_pdf, certificate):
    """PDF generation delegated to Celery."""
    generate_certificate_async.delay(certificate.id)
    mock_generate_pdf.assert_called_once()
```

### Phase 5: Coverage Analysis (1h)

**Generate Coverage Report:**

```bash
cd backend
pytest --cov=apps --cov-report=html --cov-report=term-missing

# Open HTML report
open htmlcov/index.html
```

**Identify Gaps:**

```bash
# Files below 80% coverage
coverage report --skip-covered | grep -v "100%"

# Missing lines
coverage report -m
```

**Claude Code Instructions:**

```
Task: Increase coverage for {file_path}

Current: X%
Target: >80%

Focus on:
1. Uncovered branches (if/else)
2. Exception handling
3. Edge cases
4. Error paths

Show coverage diff after each test addition.
```

### Phase 6: Final Verification (30 min)

**Full Test Suite:**

```bash
# Run all tests
pytest -v

# With coverage
pytest --cov=apps --cov-report=term --cov-report=html --cov-fail-under=80

# Specific markers
pytest -m "slow" -v
pytest -m "integration" -v
```

**Success Criteria:**
- ✅ All Postman endpoints have pytest equivalents
- ✅ Overall coverage > 80%
- ✅ Critical paths (auth, payments, enrollments) > 90%
- ✅ All tests passing
- ✅ No flaky tests (run 3 times)

**Final Commit:**

```bash
git add .
git commit -m "test: complete pytest migration from Postman

- Added Factory Boy factories for all models
- Migrated X Postman requests to pytest
- Achieved X% overall test coverage
- All apps have comprehensive test suites

Coverage by app:
- users: X%
- courses: X%
- enrollments: X%
- videos: X%
- certificates: X%

Tests: X passed in Xs"
```

## Security & Regression Deny-Tests (audit remediation)

For the 2026-06 audit fixes, the test is the **RED step** of `/fix-issue` — write the deny/
regression test first, watch it fail, then apply the layer fix. Canonical patterns below; the
per-issue gaps live in
[.claude/context/tasks/archive/audit-2026-06/remediation/07-tests.md](.claude/context/tasks/archive/audit-2026-06/remediation/07-tests.md)
(#17, #34, #50, #72, #82, #86).

### Mass-assignment ignored (#30, #39, #40)
```python
@pytest.mark.django_db
def test_register_ignores_is_instructor_flag(api_client):
    """A client cannot self-grant a privileged flag at creation."""
    resp = api_client.post("/api/auth/register/",
                           {"email": "a@b.com", "password": "Str0ng!pw", "is_instructor": True})
    assert resp.status_code == 201
    assert User.objects.get(email="a@b.com").is_instructor is False
```

### Anonymous / non-owner access denied (#41) — assert the *secure* behavior
```python
@pytest.mark.django_db
def test_user_list_denies_anonymous(api_client):
    UserFactory.create_batch(2)
    assert api_client.get("/api/users/").status_code in (401, 403)
```
> Several existing tests assert the *insecure* behavior as expected — rewrite, don't add alongside.

### Cross-object integrity (#29)
```python
def test_progress_rejects_foreign_course_lesson(api_client, enrollment, other_course_lesson):
    api_client.force_authenticate(enrollment.user)
    resp = api_client.post("/api/progress/",
                           {"enrollment": enrollment.id, "lesson": other_course_lesson.id,
                            "completed": True}, format="json")
    assert resp.status_code == 400
```

### Stripe webhook signature asserted, not mocked away (#17)
Patch one level below `verify_webhook_signature`:
```python
@patch("stripe.Webhook.construct_event")
def test_webhook_verifies_signature(mock_construct, ...):
    ... # assert called with raw body, the Stripe-Signature header, settings.STRIPE_WEBHOOK_SECRET
    mock_construct.assert_called_once()
```

### Celery task idempotency / failure (#82)
```python
def test_task_is_idempotent_when_pdf_exists(certificate_with_pdf):
    generate_certificate_pdf_async(certificate_with_pdf.id)  # eager
    assert mock_render.call_count == 0  # no regeneration

def test_task_swallows_deleted_certificate():
    generate_certificate_pdf_async(999999)  # DoesNotExist → no raise
```

### TimeStampedModel behavioral contract (#86)
```python
@pytest.mark.django_db
def test_timestamps_contract():
    obj = CourseFactory()                      # any concrete subclass
    created, updated = obj.created_at, obj.updated_at
    obj.name = "x"; obj.save()
    obj.refresh_from_db()
    assert obj.created_at == created and obj.updated_at > updated
```

**Reminders:** mock externals (Stripe, Celery `.delay`); allow + deny for every permission; assert
exact status codes (402/409/403/410); ≥90% on payments / enrollments / permissions / certificates.

## Common Patterns

### API Client Fixture

```python
# conftest.py
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def authenticated_user(api_client, user):
    api_client.force_authenticate(user=user)
    api_client.user = user
    return api_client
```

### Test Naming Convention

```
test_{action}_{condition}_{expected_result}

Examples:
- test_create_course_as_instructor_success
- test_create_course_as_student_fails
- test_enroll_in_paid_course_without_payment_returns_402
```

## Time Breakdown

- Phase 1 (Export Postman): 10 min
- Phase 2 (Setup factories): 30 min
- Phase 3 (Migrate tests):
  - users: 4-6h
  - courses: 6-8h
  - enrollments: 4-6h
  - videos: 3-4h
  - certificates: 2-3h
- Phase 4 (Coverage gaps): 1h
- Phase 5 (Verification): 30 min

**Total: 2-3 days**

## Success Message

```
✅ Automated Test Suite Complete!

Migrated X Postman requests to pytest
Achieved X% overall code coverage (target: >80%)

Coverage by app:
- users: X% (X/X lines)
- courses: X% (X/X lines)
- enrollments: X% (X/X lines)
- videos: X% (X/X lines)
- certificates: X% (X/X lines)

Next Task: Implement Payment System (TDD)
```