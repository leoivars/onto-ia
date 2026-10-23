#!/bin/sh
# Copia de seguridad de Postgres: dump comprimido, retención local y subida a Drive.
set -eu

: "${DB_HOST:?falta DB_HOST}"
: "${DB_USER:?falta DB_USER}"
: "${DB_NAME:?falta DB_NAME}"
: "${DB_PASSWORD:?falta DB_PASSWORD}"

DESTINO=/backups
RETENCION_LOCAL_DIAS=${RETENCION_LOCAL_DIAS:-14}
RETENCION_REMOTA_DIAS=${RETENCION_REMOTA_DIAS:-30}
SELLO=$(date +%Y%m%d-%H%M)
ARCHIVO="$DESTINO/onto-$SELLO.dump.gz"

mkdir -p "$DESTINO"
export PGPASSWORD="$DB_PASSWORD"

echo "[backup] $(date -Iseconds) iniciando dump de $DB_NAME"
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -Fc | gzip -9 > "$ARCHIVO"

TAMANO=$(wc -c < "$ARCHIVO")
if [ "$TAMANO" -lt 1000 ]; then
  echo "[backup] ERROR: el dump pesa $TAMANO bytes, no se sube" >&2
  rm -f "$ARCHIVO"
  exit 1
fi
echo "[backup] dump listo: $ARCHIVO ($TAMANO bytes)"

find "$DESTINO" -name 'onto-*.dump.gz' -mmin +$((RETENCION_LOCAL_DIAS * 1440)) -delete

if [ -n "${RCLONE_REMOTE:-}" ] && [ -f "${RCLONE_CONFIG:-/root/.config/rclone/rclone.conf}" ]; then
  echo "[backup] subiendo a $RCLONE_REMOTE"
  rclone copy "$ARCHIVO" "$RCLONE_REMOTE" --config "${RCLONE_CONFIG:-/root/.config/rclone/rclone.conf}"
  rclone delete "$RCLONE_REMOTE" --min-age "${RETENCION_REMOTA_DIAS}d" \
    --config "${RCLONE_CONFIG:-/root/.config/rclone/rclone.conf}" || true
  echo "[backup] subida completa"
else
  echo "[backup] sin remoto configurado: queda solo la copia local"
fi
