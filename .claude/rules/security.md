# Security Rules

## Authentication & Authorization

### Password Security

```python
# ✅ GOOD: Built-in Django password validation
# settings/base.py
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ❌ BAD: Storing passwords in plain text
user.password = request.data['password']  # NEVER!

# ✅ GOOD: Always hash passwords
user.set_password(request.data['password'])
```

### JWT Token Security

```python
# settings/base.py
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,  # Never commit SECRET_KEY!
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ❌ BAD: Long-lived access tokens
'ACCESS_TOKEN_LIFETIME': timedelta(days=30)  # Too long!

# ❌ BAD: Tokens in URL
GET /api/courses/?token=abc123  # Logged in server logs!
```

## Input Validation

### Serializer Validation

```python
from rest_framework import serializers
import re


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Secure user registration."""
    
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField()
    
    def validate_email(self, value):
        """Validate email format and uniqueness."""
        # Django already validates format via EmailField
        
        # Check uniqueness
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "User with this email already exists."
            )
        
        return value.lower()  # Normalize
    
    def validate_password(self, value):
        """Additional password validation."""
        # Django password validators will run automatically
        
        # Custom rule: no common patterns
        if re.match(r'^(password|123456|qwerty)', value, re.I):
            raise serializers.ValidationError(
                "Password too common."
            )
        
        return value
    
    def create(self, validated_data):
        """Create user with hashed password."""
        return User.objects.create_user(**validated_data)
```

### SQL Injection Prevention

```python
# ✅ GOOD: Django ORM prevents SQL injection
User.objects.filter(email=user_input)

# ✅ GOOD: Parameterized queries
User.objects.raw(
    'SELECT * FROM users WHERE email = %s',
    [user_input]
)

# ❌ BAD: String formatting in raw SQL
User.objects.raw(
    f'SELECT * FROM users WHERE email = "{user_input}"'  # VULNERABLE!
)

# ❌ BAD: Extra with user input
User.objects.extra(where=[f"email = '{user_input}'"])  # VULNERABLE!
```

### XSS Prevention

```python
# ✅ GOOD: Django templates auto-escape HTML
{{ user.name }}  # Escaped automatically

# ❌ DANGEROUS: mark_safe with user input
from django.utils.safestring import mark_safe
content = mark_safe(user_input)  # Only if sanitized!

# ✅ GOOD: Sanitize HTML if needed
import bleach

def validate_html_content(self, value):
    """Strip dangerous HTML tags."""
    allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'ol', 'li']
    return bleach.clean(value, tags=allowed_tags, strip=True)
```

## File Upload Security

### MIME Type Validation

```python
from django.core.exceptions import ValidationError
import magic


def validate_video_file(file):
    """Validate video file type using python-magic."""
    
    # Read file header
    file.seek(0)
    file_header = file.read(2048)
    file.seek(0)
    
    # Get MIME type
    mime = magic.from_buffer(file_header, mime=True)
    
    # Check against allowed types
    allowed_mimes = [
        'video/mp4',
        'video/mpeg',
        'video/quicktime',
    ]
    
    if mime not in allowed_mimes:
        raise ValidationError(
            f'Invalid video file type: {mime}. '
            f'Allowed: {", ".join(allowed_mimes)}'
        )
    
    # Check file extension (secondary check)
    ext = file.name.split('.')[-1].lower()
    if ext not in ['mp4', 'mpeg', 'mov']:
        raise ValidationError(f'Invalid file extension: .{ext}')


class Video(models.Model):
    file = models.FileField(
        upload_to='videos/',
        validators=[validate_video_file]
    )
```

### File Size Limits

```python
def validate_video_size(file):
    """Limit video file size to 500MB."""
    max_size = 500 * 1024 * 1024  # 500MB in bytes
    
    if file.size > max_size:
        raise ValidationError(
            f'File too large. Maximum size: 500MB. '
            f'Current: {file.size / (1024*1024):.1f}MB'
        )


# settings/base.py
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB in memory
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # Rest goes to temp file
```

### Safe File Storage

```python
# settings/base.py
import os

# ✅ GOOD: Store uploads outside webroot
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# ❌ BAD: Storing in static files (executed!)
# MEDIA_ROOT = os.path.join(BASE_DIR, 'static')

# Production: Use cloud storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'your-bucket'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'private'  # Not public by default
```

## HTTPS & Headers

### Force HTTPS in Production

```python
# settings/production.py

# Force HTTPS
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookie security
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

### Security Headers

```python
# settings/production.py

MIDDLEWARE += [
    'django.middleware.security.SecurityMiddleware',
]

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'  # Prevent clickjacking

# Content Security Policy (if using django-csp)
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_IMG_SRC = ("'self'", "data:", "https:")
```

## Secrets Management

### Environment Variables

```python
# ✅ GOOD: Load secrets from environment
import os
from decouple import config

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
DATABASE_PASSWORD = config('DATABASE_PASSWORD')
STRIPE_SECRET_KEY = config('STRIPE_SECRET_KEY')

# ❌ BAD: Hardcoded secrets
SECRET_KEY = 'django-insecure-abc123'  # NEVER COMMIT!
STRIPE_SECRET_KEY = 'sk_live_abc123'  # NEVER!
```

### .env File (Never Commit!)

```bash
# .env (add to .gitignore)
SECRET_KEY=your-secret-key-here
DEBUG=False
DATABASE_URL=postgresql://user:pass@localhost/db
STRIPE_SECRET_KEY=sk_test_abc123
SENTRY_DSN=https://...
```

### Checking for Secrets

```bash
# Before commit
git diff | grep -i "secret\|password\|api_key"

# Scan history (if accidentally committed)
git log -p | grep -i "secret\|password\|api_key"
```

## CSRF Protection

### CSRF Configuration

```python
# settings/base.py
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',  # Required
    ...
]

# CSRF exemption (rare cases)
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt  # Only for webhooks with signature validation
def stripe_webhook(request):
    pass
```

### CSRF with AJAX

```javascript
// ✅ GOOD: Include CSRF token in AJAX requests
fetch('/api/courses/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(data)
});

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}
```

## Rate Limiting & DDoS Protection

### Throttling Sensitive Endpoints

```python
from rest_framework.throttling import UserRateThrottle


class LoginRateThrottle(UserRateThrottle):
    """Prevent brute-force login attempts."""
    rate = '5/hour'


class PasswordResetThrottle(UserRateThrottle):
    """Prevent password reset abuse."""
    rate = '3/hour'


class RegistrationThrottle(UserRateThrottle):
    """Prevent account creation spam."""
    rate = '5/day'
```

## Logging & Monitoring

### Security Event Logging

```python
import logging

security_logger = logging.getLogger('security')


def login_view(request):
    """Log authentication attempts."""
    user = authenticate(
        username=request.data['username'],
        password=request.data['password']
    )
    
    if user:
        security_logger.info(
            f"Successful login: {user.email} from {request.META['REMOTE_ADDR']}"
        )
    else:
        security_logger.warning(
            f"Failed login attempt: {request.data['username']} "
            f"from {request.META['REMOTE_ADDR']}"
        )
```

### PII Filtering (Sentry/Logs)

```python
# settings/base.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


def strip_sensitive_data(event, hint):
    """Remove PII from Sentry reports."""
    
    # Remove password fields
    if 'request' in event and 'data' in event['request']:
        data = event['request']['data']
        if isinstance(data, dict):
            for key in ['password', 'token', 'secret', 'credit_card']:
                if key in data:
                    data[key] = '[FILTERED]'
    
    # Remove sensitive headers
    if 'request' in event and 'headers' in event['request']:
        headers = event['request']['headers']
        if 'Authorization' in headers:
            headers['Authorization'] = '[FILTERED]'
    
    return event


sentry_sdk.init(
    dsn=config('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    before_send=strip_sensitive_data,
)
```

## Database Security

### Connection Security

```python
# settings/production.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'OPTIONS': {
            'sslmode': 'require',  # Force SSL connection
        },
    }
}
```

### Prevent Mass Assignment

```python
# ❌ BAD: Accepting all user input
serializer = UserSerializer(user, data=request.data)

# ✅ GOOD: Explicit field control
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'name']  # Only these can be updated
        read_only_fields = ['is_staff', 'is_superuser']
```

## Checklist

Before deploying:

- [ ] SECRET_KEY not in version control
- [ ] DEBUG = False in production
- [ ] ALLOWED_HOSTS configured
- [ ] HTTPS enforced (SECURE_SSL_REDIRECT)
- [ ] HSTS enabled
- [ ] Secure cookies (SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE)
- [ ] File upload validation (MIME type + size)
- [ ] Rate limiting on auth endpoints
- [ ] CORS configured (no wildcard in production)
- [ ] Sentry PII filtering enabled
- [ ] Database connections use SSL
- [ ] Password validators configured
- [ ] Security headers set (CSP, X-Frame-Options)
- [ ] No secrets in logs or error messages