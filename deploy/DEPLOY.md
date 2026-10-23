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

Corre en el contenedor `onto_backup`: dump de Postgres, cifrado AES-256, retención local de 14
días y subida opcional a Google Drive con retención de 30.

La contraseña de cifrado va en `.env` como `BACKUP_PASSPHRASE`. **Sin ella no se generan
backups**; y si se pierde, los archivos viejos no se pueden abrir. Guarde una copia en un lugar
fuera del servidor (gestor de contraseñas, papel).

Restaurar:

```bash
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in onto-XXXX.dump.gz.enc \
  -pass env:BACKUP_PASSPHRASE | gunzip \
  | docker compose exec -T onto_db pg_restore -U onto -d onto --clean
```

Backup manual, sin esperar al ciclo diario:

```bash
docker compose run --rm onto_backup /usr/local/bin/backup.sh
```

Para Drive: crear `rclone.conf` en la raíz del proyecto (permiso 600, fuera de git) con la
configuración del remoto y definir `RCLONE_REMOTE=gdrive:Onto/backups` en `.env`.

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

### Leer la casilla desde el servidor

`hola@onto.xz.com.ar` reenvía a Gmail. Para consultarla sin abrir el navegador, el proyecto trae
un comando IMAP (`web/management/commands/correo.py`). Requiere una contraseña de aplicación:

1. En la cuenta de Gmail: activar verificación en dos pasos.
2. Google → Seguridad → Contraseñas de aplicaciones → generar una para "Correo IMAP".
3. Cargar en `.env` del servidor (no en el repositorio):

```
MAIL_IMAP_USER=ontoxz@gmail.com
MAIL_IMAP_PASSWORD=xxxx xxxx xxxx xxxx
MAIL_IMAP_HOST=imap.gmail.com
MAIL_IMAP_PORT=993
```

Uso:

```bash
docker compose exec -T onto_web python manage.py correo listar --limite 10
docker compose exec -T onto_web python manage.py correo listar --no-leidos
docker compose exec -T onto_web python manage.py correo leer 1234
```

La contraseña de aplicación da acceso completo al buzón. Se revoca desde la misma pantalla de
Google y conviene regenerarla cada tanto.

**Trampa al configurar Email Routing:** si la dirección de destino todavía no está verificada,
Cloudflare acepta el mensaje en el SMTP (`250`) pero lo descarta sin rebotar. Hay que abrir el mail
de verificación y confirmar el destino antes de dar por buena la recepción.

## Notas

- `ALLOWED_HOSTS=onto.xz.com.ar`: cualquier request con otro Host recibe 400.
- `DEBUG=0`: HSTS, cookies seguras y redirección a HTTPS.
- La `AI_API_KEY` vive solo en `.env` (permiso 600) y en el entorno del contenedor.
- Los estáticos se generan con hash dentro de la imagen y los sirve WhiteNoise.
- El contenedor corre como usuario sin privilegios (uid 10001) con `no-new-privileges`.
