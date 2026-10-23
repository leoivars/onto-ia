FROM postgres:16-alpine

RUN apk add --no-cache rclone gzip tzdata

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

ENTRYPOINT ["/bin/sh", "-c"]
CMD ["while true; do /usr/local/bin/backup.sh || echo '[backup] fallo, reintenta en 1h'; sleep ${BACKUP_INTERVALO:-86400}; done"]
