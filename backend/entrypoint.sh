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
email = '${DJANGO_SUPERUSER_EMAIL}'
username = '${DJANGO_SUPERUSER_USERNAME:-admin}'
if not User.objects.filter(email=email).exists() and not User.objects.filter(username=username).exists():
    User.objects.create_superuser(email=email, username=username, password='${DJANGO_SUPERUSER_PASSWORD}')
    print('✅ Superuser created: ' + email)
else:
    print('ℹ️  Superuser already exists: ' + email)
" || echo "⚠️  Superuser creation failed — continuing startup"
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