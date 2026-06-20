#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python3.12 manage.py collectstatic --noinput --clear

echo "Running migrations..."
python3.12 manage.py migrate --noinput

echo "Build complete."
