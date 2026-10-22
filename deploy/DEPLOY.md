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

Estado actual: `DEFAULT_FROM_EMAIL=Onto <agenda@turnos.xz.com.ar>`, que es la dirección aprobada.
Para pasar a `no-responder@onto.xz.com.ar`:

1. OCI → Email Delivery → Domains → agregar `onto.xz.com.ar` y verificar por TXT.
2. Generar la DKIM del dominio nuevo (CNAME de 2048 bits).
3. En Cloudflare, sobre `onto`:
   - TXT SPF: `v=spf1 include:rp.oracleemaildelivery.com include:_spf.mx.cloudflare.net ~all`
   - CNAME DKIM: el que devuelve OCI
   - TXT DMARC: `v=DMARC1; p=none; rua=mailto:dmarc@xz.com.ar`
4. Cambiar `DEFAULT_FROM_EMAIL` en `.env` y recrear el contenedor.

Para **recibir** en `hola@onto.xz.com.ar`: habilitar el subdominio en Cloudflare Email Routing y
agregar los MX `route1/2/3.mx.cloudflare.net` (10/20/30). Alternativa sin tocar nada: usar una
dirección de `xz.com.ar` que ya esté ruteada.

## Notas

- `ALLOWED_HOSTS=onto.xz.com.ar`: cualquier request con otro Host recibe 400.
- `DEBUG=0`: HSTS, cookies seguras y redirección a HTTPS.
- La `AI_API_KEY` vive solo en `.env` (permiso 600) y en el entorno del contenedor.
- Los estáticos se generan con hash dentro de la imagen y los sirve WhiteNoise.
- El contenedor corre como usuario sin privilegios (uid 10001) con `no-new-privileges`.
