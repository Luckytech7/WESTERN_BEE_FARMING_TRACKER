#!/bin/bash
set -e

echo "Installing dependencies..."
uv pip install --system -r requirements.txt

echo "Running migrations..."
uv run python manage.py migrate --noinput

echo "Collecting static files..."
uv run python manage.py collectstatic --noinput --clear

echo "Build complete."
