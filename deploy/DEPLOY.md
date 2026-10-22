# Publicar Onto en onto.zx.com.ar

El dominio `zx.com.ar` está detrás de Cloudflare. El subdominio no se compra: se crea un
registro DNS y se apunta al servidor donde corre Django.

## 1. DNS en Cloudflare

Panel de Cloudflare → zona `zx.com.ar` → DNS → Add record:

- **Type:** A
- **Name:** `onto`
- **IPv4:** IP pública del servidor
- **Proxy status:** Proxied (nube naranja)
- **TTL:** Auto

Verificar desde cualquier máquina:

```bash
dig +short onto.zx.com.ar
```

Con el proxy activo devuelve IPs de Cloudflare (104.x / 172.67.x). Es correcto.

## 2. Certificado

Con la nube naranja, el TLS lo termina Cloudflare y el origen necesita un certificado válido
para el modo **Full (strict)**:

1. Cloudflare → SSL/TLS → Origin Server → Create Certificate. Hostnames:
   `onto.zx.com.ar`. Validez: 15 años.
2. Guardar en el servidor:

```bash
sudo mkdir -p /etc/ssl/onto
sudo nano /etc/ssl/onto/origin.pem   # pegar el certificado
sudo nano /etc/ssl/onto/origin.key   # pegar la clave privada
sudo chmod 600 /etc/ssl/onto/origin.key
```

3. SSL/TLS → Overview → modo **Full (strict)**. Activar «Always Use HTTPS».

Alternativa sin Cloudflare: poner el registro en gris (DNS only) y emitir Let's Encrypt:

```bash
sudo certbot --nginx -d onto.zx.com.ar
```

## 3. Servidor

```bash
sudo adduser --system --group --home /srv/onto onto
sudo mkdir -p /srv/onto && sudo chown onto:onto /srv/onto
# subir el proyecto a /srv/onto (rsync, git clone o scp)
cd /srv/onto
sudo -u onto python3 -m venv .venv
sudo -u onto .venv/bin/pip install -r requirements.txt
```

Crear `/srv/onto/.env` (formato `KEY=valor`, sin comillas: systemd lo lee tal cual):

```
SECRET_KEY=<cadena larga aleatoria>
DEBUG=0
ALLOWED_HOSTS=onto.zx.com.ar
CSRF_TRUSTED_ORIGINS=https://onto.zx.com.ar
SITE_NAME=Onto
SITE_DOMAIN=onto.zx.com.ar
CONTACT_EMAIL=hola@onto.zx.com.ar
AI_API_KEY=<clave del proveedor>
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4.1-mini
AI_PRICE_IN=0.40
AI_PRICE_OUT=1.60
```

```bash
sudo -u onto .venv/bin/python manage.py migrate --noinput
sudo -u onto .venv/bin/python manage.py collectstatic --noinput
sudo -u onto .venv/bin/python manage.py createsuperuser
```

Generar la `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(56))"
```

## 4. Servicios

```bash
sudo cp deploy/onto.service /etc/systemd/system/onto.service
sudo systemctl daemon-reload
sudo systemctl enable --now onto

sudo cp deploy/nginx-onto.conf /etc/nginx/sites-available/onto
sudo ln -sf /etc/nginx/sites-available/onto /etc/nginx/sites-enabled/onto
sudo nginx -t && sudo systemctl reload nginx
```

Firewall: permitir 80 y 443. Gunicorn escucha solo en 127.0.0.1:8001.

## 5. Verificación

```bash
curl -I https://onto.zx.com.ar
curl -s https://onto.zx.com.ar/robots.txt
curl -s https://onto.zx.com.ar/sitemap.xml | head
curl -s https://onto.zx.com.ar/ | grep -o 'canonical" href="[^"]*"'
```

Esperado: 200, canonical apuntando a `https://onto.zx.com.ar/`, y el CSS con hash
(`/static/css/app.<hash>.css`) respondiendo 200.

Después: registrar el sitio en Google Search Console (propiedad de prefijo de URL
`https://onto.zx.com.ar`), enviar el sitemap y verificar que `/panel/`, `/cuenta/` y
`/informes/` estén como `noindex`.

## 6. Actualizaciones

```bash
cd /srv/onto && ./deploy/deploy.sh
```

## Nota sobre el subdominio y el SEO

Google trata `onto.zx.com.ar` como un sitio distinto de `zx.com.ar` a efectos de autoridad.
Conviene:

- enlazar desde `zx.com.ar` al subdominio con un enlace visible y permanente;
- mantener el canonical a `https://onto.zx.com.ar` (ya está en todas las páginas);
- no duplicar el contenido en otro subdominio ni en el dominio raíz;
- enviar el sitemap y revisar cobertura en Search Console.

Si en el futuro el producto crece, moverlo a un dominio propio (`onto.com.ar`) conserva la
autoridad acumulada con redirecciones 301 página por página.
