#!/bin/sh
# Verifica que el backup diario exista, sea reciente y esté en el remoto.
set -eu

DESTINO=/backups
MAX_HORAS=${MAX_HORAS:-36}
CONF="${RCLONE_CONFIG:-/root/.config/rclone/rclone.conf}"

ULTIMO=$(ls -t "$DESTINO"/onto-*.dump.gz.enc 2>/dev/null | head -1 || true)
if [ -z "$ULTIMO" ]; then
  echo "FALLA: no hay ningún backup local"
  exit 1
fi

EDAD=$(( ($(date +%s) - $(stat -c %Y "$ULTIMO")) / 3600 ))
if [ "$EDAD" -gt "$MAX_HORAS" ]; then
  echo "FALLA: el backup local más nuevo tiene ${EDAD}h (máximo ${MAX_HORAS}h)"
  exit 1
fi

NOMBRE=$(basename "$ULTIMO")
TAMANO=$(wc -c < "$ULTIMO")
if [ "$TAMANO" -lt 1000 ]; then
  echo "FALLA: $NOMBRE pesa $TAMANO bytes"
  exit 1
fi

if [ -z "${RCLONE_REMOTE:-}" ]; then
  echo "OK parcial: $NOMBRE (${EDAD}h, $TAMANO bytes) sin remoto configurado"
  exit 0
fi

if ! LISTADO=$(rclone lsf "$RCLONE_REMOTE" --files-only --config "$CONF" 2>&1); then
  echo "FALLA: no se pudo listar $RCLONE_REMOTE"
  echo "$LISTADO" | tail -3
  exit 1
fi

if ! echo "$LISTADO" | grep -qx "$NOMBRE"; then
  echo "FALLA: $NOMBRE no está en $RCLONE_REMOTE"
  exit 1
fi

echo "OK: $NOMBRE (${EDAD}h, $TAMANO bytes) presente en el remoto"
