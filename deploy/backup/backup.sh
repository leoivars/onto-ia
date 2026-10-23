#!/bin/sh
# Copia de seguridad de Postgres: dump, cifrado, retención y subida opcional a Drive.
set -eu

: "${DB_HOST:?falta DB_HOST}"
: "${DB_USER:?falta DB_USER}"
: "${DB_NAME:?falta DB_NAME}"
: "${DB_PASSWORD:?falta DB_PASSWORD}"
: "${BACKUP_PASSPHRASE:?falta BACKUP_PASSPHRASE: no se guardan backups sin cifrar}"

DESTINO=/backups
RETENCION_LOCAL_DIAS=${RETENCION_LOCAL_DIAS:-14}
RETENCION_REMOTA_DIAS=${RETENCION_REMOTA_DIAS:-30}
ITERACIONES=${BACKUP_ITERACIONES:-200000}
SELLO=$(date +%Y%m%d-%H%M)
PLANO="$DESTINO/onto-$SELLO.dump.gz"
CIFRADO="$PLANO.enc"

# Si algo falla, el dump en claro no queda en disco.
trap 'rm -f "$PLANO"' EXIT

mkdir -p "$DESTINO"
export PGPASSWORD="$DB_PASSWORD"

echo "[backup] $(date -Iseconds) dump de $DB_NAME"
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -Fc | gzip -9 > "$PLANO"

openssl enc -aes-256-cbc -pbkdf2 -iter "$ITERACIONES" -salt \
  -in "$PLANO" -out "$CIFRADO" -pass env:BACKUP_PASSPHRASE
rm -f "$PLANO"

TAMANO=$(wc -c < "$CIFRADO")
if [ "$TAMANO" -lt 1000 ]; then
  echo "[backup] ERROR: el archivo cifrado pesa $TAMANO bytes" >&2
  rm -f "$CIFRADO"
  exit 1
fi
chmod 600 "$CIFRADO"
echo "[backup] listo: $CIFRADO ($TAMANO bytes, cifrado)"

find "$DESTINO" -name 'onto-*.dump.gz.enc' -mmin +$((RETENCION_LOCAL_DIAS * 1440)) -delete

CONF="${RCLONE_CONFIG:-/root/.config/rclone/rclone.conf}"
if [ -n "${RCLONE_REMOTE:-}" ] && [ -f "$CONF" ] && [ -s "$CONF" ]; then
  echo "[backup] subiendo a $RCLONE_REMOTE"
  rclone copy "$CIFRADO" "$RCLONE_REMOTE" --config "$CONF"
  rclone delete "$RCLONE_REMOTE" --min-age "${RETENCION_REMOTA_DIAS}d" --config "$CONF" || true
  echo "[backup] subida completa"
else
  echo "[backup] sin remoto configurado: queda solo la copia local cifrada"
fi
