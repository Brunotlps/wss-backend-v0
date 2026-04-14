#!/bin/bash

# Exit on error
set -e

echo "🔍 Waiting for PostgreSQL to be ready..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "✅ PostgreSQL is ready!"

echo "🔄 Running database migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "👤 Creating superuser if it doesn't exist..."
if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='${DJANGO_SUPERUSER_EMAIL}').exists():
    User.objects.create_superuser(
        email='${DJANGO_SUPERUSER_EMAIL}',
        username='${DJANGO_SUPERUSER_USERNAME:-admin}',
        password='${DJANGO_SUPERUSER_PASSWORD}'
    )
    print('✅ Superuser created: ${DJANGO_SUPERUSER_EMAIL}')
else:
    print('ℹ️  Superuser already exists: ${DJANGO_SUPERUSER_EMAIL}')
"
else
    echo "⚠️  DJANGO_SUPERUSER_EMAIL/PASSWORD not set — skipping superuser creation"
fi

echo "🚀 Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -