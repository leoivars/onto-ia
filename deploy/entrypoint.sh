#!/bin/sh
# Arranque del contenedor: aplica migraciones y cede el proceso a gunicorn.
set -e

echo "[onto] aplicando migraciones"
python manage.py migrate --noinput

echo "[onto] iniciando: $*"
exec "$@"
