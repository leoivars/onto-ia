FROM postgres:16-alpine

RUN apk add --no-cache rclone gzip tzdata openssl

COPY backup.sh /usr/local/bin/backup.sh
COPY verificar.sh /usr/local/bin/verificar.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/verificar.sh

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["while true; do if /usr/local/bin/backup.sh; then sleep ${BACKUP_INTERVALO:-86400}; else echo '[backup] fallo, reintento en 1h'; sleep 3600; fi; done"]
