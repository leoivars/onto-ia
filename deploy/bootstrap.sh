#!/usr/bin/env bash
# Bootstrap del servidor (Debian/Ubuntu, ejecutar como root).
# Uso: sudo ./deploy/bootstrap.sh
# Idempotente: se puede correr dos veces.
set -euo pipefail

APP_DIR=/srv/onto
APP_USER=onto
PY=python3

if [[ $EUID -ne 0 ]]; then
  echo "Ejecutar como root: sudo ./deploy/bootstrap.sh" >&2
  exit 1
fi

echo "==> Paquetes"
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx rsync curl ca-certificates

echo "==> Usuario y directorio"
id -u "$APP_USER" >/dev/null 2>&1 || adduser --system --group --home "$APP_DIR" "$APP_USER"
mkdir -p "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

if [[ ! -f "$APP_DIR/manage.py" ]]; then
  echo "El código todavía no está en $APP_DIR." >&2
  echo "Subilo primero (rsync o git clone) y volvé a correr este script." >&2
  exit 1
fi

echo "==> Entorno virtual"
[[ -d "$APP_DIR/.venv" ]] || sudo -u "$APP_USER" "$PY" -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "==> Falta $APP_DIR/.env"
  echo "    Copiá .env.example, completá SECRET_KEY y AI_API_KEY, y volvé a correr."
  exit 1
fi

echo "==> Migraciones y estáticos"
cd "$APP_DIR"
sudo -u "$APP_USER" env $(grep -v '^#' .env | xargs) .venv/bin/python manage.py migrate --noinput
sudo -u "$APP_USER" env $(grep -v '^#' .env | xargs) .venv/bin/python manage.py collectstatic --noinput

echo "==> systemd"
install -m 644 "$APP_DIR/deploy/onto.service" /etc/systemd/system/onto.service
systemctl daemon-reload
systemctl enable --now onto

echo "==> nginx"
install -m 644 "$APP_DIR/deploy/nginx-onto.conf" /etc/nginx/sites-available/onto
ln -sf /etc/nginx/sites-available/onto /etc/nginx/sites-enabled/onto
nginx -t
systemctl reload nginx

echo
echo "Listo. Falta el certificado en /etc/ssl/onto/origin.pem y .key (ver deploy/DEPLOY.md)."
echo "Después: curl -I https://${SITE_DOMAIN:-onto.zx.com.ar}"
