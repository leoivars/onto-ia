#!/usr/bin/env bash
# Despliegue de Onto en el servidor. Uso: ./deploy/deploy.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/onto}"
cd "$APP_DIR"

echo "==> Dependencias"
.venv/bin/pip install -q -r requirements.txt

echo "==> Variables"
set -a
# .env debe tener formato KEY=valor (sin espacios ni comillas) para systemd.
. ./.env
set +a

echo "==> Migraciones"
.venv/bin/python manage.py migrate --noinput

echo "==> Estáticos"
.venv/bin/python manage.py collectstatic --noinput

echo "==> Reinicio"
sudo systemctl restart onto
sudo systemctl --no-pager --lines=5 status onto

echo "==> Verificación"
sleep 2
curl -fsS -o /dev/null -w "landing: %{http_code}\n" "https://${SITE_DOMAIN}/"
curl -fsS -o /dev/null -w "robots:  %{http_code}\n" "https://${SITE_DOMAIN}/robots.txt"
curl -fsS -o /dev/null -w "sitemap: %{http_code}\n" "https://${SITE_DOMAIN}/sitemap.xml"
echo "OK"
