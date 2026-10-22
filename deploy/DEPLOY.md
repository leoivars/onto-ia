# Despliegue de Onto (Docker)

## Arquitectura en el servidor

```
Internet → Cloudflare → gateway_caddy (80/443, compartido) → 127.0.0.1:8020 → onto_web
                                                                              └→ onto_db (Postgres, red interna)
```

- `onto_web`: imagen `onto-app`, gunicorn en 8000, publicado en **8020**.
- `onto_db`: `postgres:16-alpine`, sin puerto publicado, volumen `onto_db`.
- Todo vive en `/home/ubuntu/onto`. No se toca ningún otro proyecto del servidor.
- El enrutado por hostname se hace en el Caddy compartido: ver `deploy/CADDY.md`.

## Primer despliegue

```bash
ssh ubuntu@163.176.237.182
mkdir -p ~/onto && cd ~/onto
# copiar el proyecto (tar/rsync/git)
cp .env.example .env && chmod 600 .env
# completar SECRET_KEY, DB_PASSWORD y AI_API_KEY
docker compose build
docker compose up -d
```

Generar secretos:

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 24   # DB_PASSWORD
```

El entrypoint aplica migraciones al arrancar. Para crear el administrador:

```bash
docker compose run --rm onto_web python manage.py createsuperuser
```

## Actualizar

```bash
cd ~/onto
docker compose build && docker compose up -d
```

El `up -d` recrea solo lo que cambió. Postgres conserva el volumen.

## Operación

```bash
docker compose ps
docker compose logs -f --tail=100 onto_web
docker compose exec onto_web python manage.py check --deploy
```

## Backup y restauración

```bash
# backup
docker compose exec -T onto_db pg_dump -U onto onto | gzip > ~/onto/backup-$(date +%F).sql.gz

# restaurar
gunzip -c backup-2026-10-22.sql.gz | docker compose exec -T onto_db psql -U onto onto
```

Guardar los backups fuera del servidor: son datos personales sensibles (Ley 25.326).

## Correo

El envío usa **OCI Email Delivery** por SMTP (`smtp.email.sa-saopaulo-1.oci.oraclecloud.com:587`),
con las mismas credenciales del proyecto turnovip. La autenticación funciona, pero OCI solo acepta
remitentes de dominios aprobados en la consola.

Estado actual: remitente activo `Onto <no-responder@onto.xz.com.ar>`. En Cloudflare están
publicados el SPF (Oracle + Cloudflare), el CNAME de DKIM (`onto2026._domainkey.onto`) y DMARC en
`p=none`. OCI tiene aprobado el dominio y el envío real fue aceptado.

Verificar entregabilidad mirando el mensaje original en el cliente: `spf=pass` y `dkim=pass`
(alineado con `onto.xz.com.ar`). Cuando eso esté confirmado y haya volumen real, pasar DMARC a
`p=quarantine`.

Para recibir en `onto.xz.com.ar` está habilitado Email Routing en el subdominio (MX `route1/2/3`
con prioridades 23/37/75) y la regla `hola@onto.xz.com.ar → ontoxz@gmail.com`. El SPF del
subdominio ya incluye `_spf.mx.cloudflare.net`, así que el reenvío está autorizado. El contacto
público del sitio es esa dirección.

Si en el futuro se agrega un formulario de contacto con volumen, conviene pasarlo a un Email
Worker que lo entregue a la app en lugar de depender del reenvío a Gmail.

## Notas

- `ALLOWED_HOSTS=onto.xz.com.ar`: cualquier request con otro Host recibe 400.
- `DEBUG=0`: HSTS, cookies seguras y redirección a HTTPS.
- La `AI_API_KEY` vive solo en `.env` (permiso 600) y en el entorno del contenedor.
- Los estáticos se generan con hash dentro de la imagen y los sirve WhiteNoise.
- El contenedor corre como usuario sin privilegios (uid 10001) con `no-new-privileges`.
