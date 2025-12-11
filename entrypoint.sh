#!/bin/bash

# Salir inmediatamente si un comando falla (importante para migraciones)
set -e

echo "Running Django migrations..."
python manage.py migrate

echo "Starting Gunicorn server..."
# exec reemplaza el proceso actual con Gunicorn, asegurando que sea el proceso principal del contenedor.
exec python -m gunicorn core.wsgi:application --bind 0.0.0.0:8080 --workers 1 --threads 1