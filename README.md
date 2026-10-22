# Onto

Coaching ontológico asistido por IA, en `https://onto.zx.com.ar`. El usuario completa una
entrevista de 37 preguntas, el sistema escribe un informe ontológico de nueve secciones y el
usuario lo devuelve con feedback para generar una profundización. Suscripción mensual con
cuota de informes.

Despliegue del subdominio paso a paso: [`deploy/DEPLOY.md`](deploy/DEPLOY.md).

## Stack

- Django 6.1 + Postgres 16 en Docker (SQLite para desarrollo local y tests)
- Sin dependencias de frontend: HTML server-rendered + un CSS propio
- Motor de IA por API compatible con OpenAI (funciona también con DeepSeek, Groq, etc.)
- Motor local de respaldo: si no hay `AI_API_KEY`, el sitio genera un informe con plantillas
  reales para poder probar el flujo completo sin costo
- Despliegue: `docker compose` en el servidor, detrás del Caddy compartido

## Cómo correrlo

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env          # completar variables (no commitear)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Abrir http://127.0.0.1:8000.

Cuenta de demostración (entrevista completa, plan Profundo y un informe generado):

```bash
.venv/bin/python manage.py crear_demo
# demo@observador.test / Demo2026!
```

## Activar el motor de IA

Definir en el entorno:

```
AI_API_KEY=...
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4.1-mini
```

La clave no se guarda en la base ni en el código: se lee de `os.environ`. Si la llamada
falla, el sistema no rompe: cae al motor local y lo informa en pantalla.

## Estructura

```
web/       landing, precios, legales, cuenta, panel, códigos de invitación, leads
intake/    preguntas (7 bloques, 37 preguntas), respuestas, progreso, señales de riesgo
reports/   modelos, motor local, cliente de IA, render Markdown, vistas de informe
templates/ base + web + intake + reports
static/    css/app.css
```

## Modelo de negocio implementado

| Plan | Precio | Informes/mes |
|---|---|---|
| Gratuito | $0 | 1 |
| Profundo | $6.900 | 8 |
| Estudio | $24.900 | 40 |

Los códigos de invitación (`InviteCode`, se crean desde /admin) activan 30 días de plan pago
sin pasar por checkout: es el mecanismo para el acceso anticipado mientras no haya cuenta de
pagos. La cuota se controla en `Profile.puede_generar` y en `reports.views.generar`.

Costo real por informe (estimado con precios configurables `AI_PRICE_IN`/`AI_PRICE_OUT`):
un informe típico consume ~5.000 tokens de entrada y ~2.000 de salida. Con un modelo tipo
`gpt-4.1-mini` son centavos de dólar; el margen del plan Observador es amplio incluso con
8 informes.

## Antes de vender: pendientes

1. **Marca y dominio.** Resuelto: `Onto` en `onto.zx.com.ar` (subdominio de `zx.com.ar`,
   gestionado en Cloudflare). Falta crear el registro A y el certificado de origen.
2. **Cuenta de pagos.** Mercado Pago (Checkout Pro + Suscripciones) para ARS; Stripe para
   exterior. Falta implementar el checkout y el webhook de confirmación.
3. **Legales.** Los textos cubren Ley 25.326 (datos sensibles, consentimiento expreso,
   derechos, AAIP), Ley 24.240 y Res. 424/2020 (botón de arrepentimiento). Antes de publicar:
   revisión por abogado, inscripción de la base de datos ante la AAIP y datos del responsable.
4. **Transparencia de IA.** El sitio declara en landing, precios y cada informe que el texto lo
   produce un modelo. Mantenerlo: no presentarlo como un coach humano.
5. **Crisis.** Hay detección de señales de riesgo y bloque de derivación (911, 0800-333-2424).
   Definir protocolo interno y responsables antes de abrir al público.
6. **Producción.** Postgres, `DEBUG=0`, `ALLOWED_HOSTS`, gunicorn detrás de nginx o Railway,
   backups, y rotación de `SECRET_KEY` fuera del repo.

## Deploy mínimo (Hetzner / VPS)

```bash
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3
```

Nginx sirve `/static/` desde `staticfiles/` y hace proxy al puerto 8001.

## Pruebas

```bash
.venv/bin/python manage.py test
```

13 pruebas: flujo completo (registro, entrevista, informe, cuota, canje, feedback, exportación,
borrado), SEO, host no permitido y motor de IA con proveedor simulado. Corren en CI en cada push
(`.gitlab-ci.yml`), junto con `check` y `makemigrations --check`.
