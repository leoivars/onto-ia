FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN addgroup --system --gid 10001 onto \
    && adduser --system --uid 10001 --ingroup onto --home /app onto

RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=onto:onto . .

# Estáticos con hash dentro de la imagen (WhiteNoise los sirve).
RUN SECRET_KEY=build-only DEBUG=0 python manage.py collectstatic --noinput \
    && mkdir -p /app/data && chown -R onto:onto /app

COPY --chown=onto:onto deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER onto
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8000), 3)" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
