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
python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser(
        email='admin@example.com',
        username='admin',
        password='admin123'
    );
    print('✅ Superuser created!')
else:
    print('ℹ️  Superuser already exists')
"

echo "🚀 Starting Gunicorn..."
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers ${GUNICORN_WORKERS:-3} \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile -