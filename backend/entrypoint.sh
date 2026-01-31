#!/bin/bash
set -e

echo "Running checks"
python manage.py check

echo "Running Django migrations..."
python manage.py migrate --noinput

# With confirmation prompt (recommended):
python manage.py clear_inventory


echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000
