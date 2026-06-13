# Command: PEP8 Code Review

## Objective

Execute systematic PEP8 validation across all Django apps, fixing code style issues one app at a time using TDD workflow.

**Dependencies:**
- See: [.claude/rules/code-style.md](.claude/rules/code-style.md) (PEP8 conventions)
- See: [.claude/rules/testing.md](.claude/rules/testing.md) (Test patterns)
- See: [.claude/rules/django-patterns.md](.claude/rules/django-patterns.md) (Django best practices)

## Prerequisites

- [ ] Linters configured (flake8, black, isort, pylint)
- [ ] Virtual environment activated
- [ ] All tests passing before starting
- [ ] Git working tree clean (commit current work)

## Workflow

### Phase 0: Configure Linters (10 min - one time setup)

**Create pyproject.toml (black + isort config):**

```bash
cat > backend/pyproject.toml << 'EOF'
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | venv
  | migrations
  | __pycache__
  | build
  | dist
)/
'''

[tool.isort]
profile = "black"
line_length = 88
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true
skip_glob = ["*/migrations/*"]
known_django = "django"
known_drf = "rest_framework"
sections = ["FUTURE", "STDLIB", "DJANGO", "DRF", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]

[tool.pytest.ini_options]
python_files = "test_*.py"
testpaths = ["apps"]
DJANGO_SETTINGS_MODULE = "config.settings.development"
addopts = "--cov=apps --cov-report=term --cov-report=html --cov-fail-under=80 -v"
EOF
```

**Create .flake8 config:**

```bash
cat > backend/.flake8 << 'EOF'
[flake8]
max-line-length = 88
extend-ignore = E203, W503
exclude =
    .git,
    __pycache__,
    */migrations/*,
    venv,
    .venv,
    build,
    dist,
    *.egg-info
max-complexity = 10
per-file-ignores =
    __init__.py:F401
EOF
```

**Verify configuration:**

```bash
cd backend
cat pyproject.toml
cat .flake8
```

### Phase 1: Setup (5 min)

1. **Create checkpoint:**
   ```bash
   git add -A
   git commit -m "chore: checkpoint before PEP8 review"
   ```

2. **Verify linters installed:**
   ```bash
   pip list | grep -E "flake8|black|isort|pylint"
   ```

3. **Run baseline check:**
   ```bash
   flake8 backend/apps/ --count --statistics
   black --check backend/apps/
   isort --check backend/apps/
   ```

### Phase 2: App-by-App Review (4-6h total)

**Apps Priority Order:**
1. `apps/users/` (foundation - 30-45 min)
2. `apps/courses/` (core domain - 45-60 min)
3. `apps/videos/` (file handling - 30-45 min)
4. `apps/enrollments/` (relationships - 30-45 min)
5. `apps/certificates/` (PDF generation - 30-45 min)

**For Each App:**

```bash
# 1. Analyze current issues
APP=users
flake8 backend/apps/$APP/ > /tmp/$APP-flake8.txt
cat /tmp/$APP-flake8.txt

# 2. Check line length violations
flake8 backend/apps/$APP/ --select=E501

# 3. Check import organization
isort backend/apps/$APP/ --check --diff

# 4. Run pylint for deep analysis
pylint backend/apps/$APP/ --output-format=text --score=yes
```

**Claude Code Instructions:**

```
Task: Fix PEP8 issues in apps/{APP_NAME}/

Reference:
- .claude/rules/code-style.md (MUST follow these conventions)
- backend/pyproject.toml (Black + isort settings)
- backend/.flake8 (PEP8 rules)

Rules:
1. Follow .claude/rules/code-style.md strictly
2. Fix issues in this order:
   a) Import organization (isort)
   b) Line length (E501)
   c) Whitespace (E2xx, W2xx)
   d) Naming conventions
   e) Docstrings
   f) Type hints

3. ONE file at a time
4. Show diff before applying
5. Run tests after each file
6. Ask permission for every change

Safety:
- Never delete code without confirmation
- Preserve existing logic
- Add comments for complex refactoring

Start with: apps/{APP_NAME}/models.py
```

**Fix Pattern:**

```bash
# Step 1: Auto-fix imports
isort backend/apps/$APP/

# Step 2: Auto-format code
black backend/apps/$APP/

# Step 3: Verify
flake8 backend/apps/$APP/

# Step 4: Run tests
pytest backend/apps/$APP/tests/ -v

# Step 5: Commit
git add backend/apps/$APP/
git commit -m "style(${APP}): apply PEP8 and code formatting

- Organize imports with isort
- Format code with black (88 char lines)
- Fix flake8 violations
- Add missing docstrings
- Add type hints

Tests: All passing"
```

### Phase 3: Verification (15 min)

**Full Project Check:**

```bash
# 1. Run all linters
flake8 backend/apps/ --statistics
black --check backend/apps/
isort --check backend/apps/

# 2. Run full test suite
cd backend
pytest --cov=apps --cov-report=term --cov-report=html

# 3. Check coverage
open htmlcov/index.html  # Or check terminal output

# 4. Pylint final score
pylint backend/apps/ --score=yes | grep "Your code"
```

**Success Criteria:**
- ✅ flake8: 0 errors
- ✅ black: All files formatted
- ✅ isort: All imports organized
- ✅ pylint: Score > 9.0
- ✅ pytest: All tests passing
- ✅ Coverage: > 80%

### Phase 4: Documentation (5 min)

**Update Planning Docs:**

```bash
# Update DETAILS_PLAN.md
echo "- ✅ Task X: PEP8 Validation - Code quality audit complete" >> backend/planning_deploy/DETAILS_PLAN.md
```

**Create Summary:**

```markdown
## PEP8 Review Summary

**Date:** 2026-04-07
**Duration:** Xh Xmin

**Changes:**
- apps/users: X files, Y issues fixed
- apps/courses: X files, Y issues fixed
- apps/videos: X files, Y issues fixed
- apps/enrollments: X files, Y issues fixed
- apps/certificates: X files, Y issues fixed

**Metrics:**
- Lines formatted: X
- Imports reorganized: Y
- Docstrings added: Z
- Type hints added: W

**Final Scores:**
- flake8: 0 errors
- pylint: 9.X/10
- Coverage: X%

**Commits:** See git log
```

## Common Issues & Fixes

### Line Length (E501)

```python
# ❌ BAD (>88 chars)
def create_enrollment(user, course, payment_status, completion_percentage, enrolled_at):
    pass

# ✅ GOOD (Black formatted)
def create_enrollment(
    user,
    course,
    payment_status,
    completion_percentage,
    enrolled_at
):
    pass
```

### Import Organization (I001, I003)

```python
# ❌ BAD
import os
from .models import Course
from django.db import models
from rest_framework import serializers
import sys

# ✅ GOOD (isort)
import os
import sys

from django.db import models
from rest_framework import serializers

from .models import Course
```

### Missing Docstrings (D100-D107)

```python
# ❌ BAD
def calculate_progress(enrollment):
    return (enrollment.completed_videos / enrollment.total_videos) * 100

# ✅ GOOD
def calculate_progress(enrollment) -> float:
    """Calculate enrollment completion percentage.
    
    Args:
        enrollment: Enrollment instance with completed/total video counts.
    
    Returns:
        Float between 0-100 representing completion percentage.
    """
    return (enrollment.completed_videos / enrollment.total_videos) * 100
```

### Trailing Whitespace (W291, W293)

```python
# ❌ BAD (spaces after code)
def my_function():␣␣
    pass␣

# ✅ GOOD (black auto-fixes)
def my_function():
    pass
```

## Rollback Plan

If tests fail after formatting:

```bash
# 1. Check what changed
git diff

# 2. Reset specific file
git checkout -- backend/apps/users/models.py

# 3. Reset entire app
git checkout -- backend/apps/users/

# 4. Reset all changes
git reset --hard HEAD
```

## Time Estimates

**Per App:**
- Small (users, certificates): 30-45 min
- Medium (courses, videos, enrollments): 45-60 min

**Total:** 4-6 hours (including breaks and verification)

## Success Message

```
✅ PEP8 Code Review Complete!

All Django apps now follow PEP8 conventions:
- Consistent formatting (Black 88-char style)
- Organized imports (stdlib → third-party → local)
- Complete docstrings (Google style)
- Type hints on function signatures
- No flake8 violations

Next Task: Create Automated Tests (pytest migration)
```