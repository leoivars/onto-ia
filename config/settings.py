"""Configuración del proyecto Observador (MVP)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-cambiar-en-produccion")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get(
    "ALLOWED_HOSTS", "onto.xz.com.ar,localhost,127.0.0.1,testserver").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get(
    "CSRF_TRUSTED_ORIGINS", "https://onto.xz.com.ar").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "web.apps.WebConfig",
    "intake",
    "reports",
    "pagos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "web.context.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# En Docker/Producción se usa Postgres (DB_HOST define el cambio).
if os.environ.get("DB_HOST"):
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "onto"),
        "USER": os.environ.get("DB_USER", "onto"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ["DB_HOST"],
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Mendoza"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "panel"
LOGOUT_REDIRECT_URL = "landing"

# ------------------------- Marca y producto -------------------------
SITE_NAME = os.environ.get("SITE_NAME", "Onto")
SITE_TAGLINE = "Coaching ontológico asistido por IA"
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "onto.xz.com.ar")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "hola@onto.xz.com.ar")

# Cuota de informes por mes según plan
PLAN_QUOTA = {"free": 1, "pro": 8, "estudio": 40}
PLAN_PRICE_ARS = {"free": 0, "pro": 6900, "estudio": 24900}
PLAN_NOMBRES = {"free": "Gratuito", "pro": "Profundo", "estudio": "Estudio"}

# ------------------------- Mercado Pago -------------------------
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
MP_PUBLIC_KEY = os.environ.get("MP_PUBLIC_KEY", "")
MP_WEBHOOK_SECRET = os.environ.get("MP_WEBHOOK_SECRET", "")
MP_API = os.environ.get("MP_API", "https://api.mercadopago.com")

# ------------------------- Etapa del producto -------------------------
# Con PAGOS_ACTIVOS=0 el sitio funciona en beta: no se puede pagar y el acceso
# se otorga con códigos de invitación. Se activa cuando haya validación.
PAGOS_ACTIVOS = os.environ.get("PAGOS_ACTIVOS", "0") == "1"
MODO_BETA = not PAGOS_ACTIVOS

# ------------------------- Motor de IA -------------------------
# La clave NUNCA se guarda en el código: se inyecta por variable de entorno.
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = os.environ.get("AI_MODEL", "deepseek-flash")
AI_MODEL_PREMIUM = os.environ.get("AI_MODEL_PREMIUM", "deepseek-v4-pro")
AI_PREMIUM_CUPO = int(os.environ.get("AI_PREMIUM_CUPO", "2"))
AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "120"))
AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "8000"))
# El razonamiento interno consume la ventana de salida y trunca el informe.
AI_THINKING = os.environ.get("AI_THINKING", "disabled")
# Precios por millón de tokens (horario valle).
AI_PRICE_IN = float(os.environ.get("AI_PRICE_IN", "0.15"))
AI_PRICE_OUT = float(os.environ.get("AI_PRICE_OUT", "0.60"))
AI_PRICE_CACHE_IN = float(os.environ.get("AI_PRICE_CACHE_IN", "0.003"))
AI_PRICE_PREMIUM_IN = float(os.environ.get("AI_PRICE_PREMIUM_IN", "0.66"))
AI_PRICE_PREMIUM_OUT = float(os.environ.get("AI_PRICE_PREMIUM_OUT", "1.98"))
AI_PRICE_PREMIUM_CACHE_IN = float(os.environ.get("AI_PRICE_PREMIUM_CACHE_IN", "0.022"))
AI_PRECIOS = {
    AI_MODEL: {"in": AI_PRICE_IN, "out": AI_PRICE_OUT, "cache": AI_PRICE_CACHE_IN},
    AI_MODEL_PREMIUM: {
        "in": AI_PRICE_PREMIUM_IN, "out": AI_PRICE_PREMIUM_OUT,
        "cache": AI_PRICE_PREMIUM_CACHE_IN},
}
# DeepSeek duplica tarifas en horas pico (01-04 y 06-10 UTC, lunes a viernes).
AI_PRICE_PEAK_MULT = float(os.environ.get("AI_PRICE_PEAK_MULT", "2.0"))
# Presupuesto de contexto por informe, en caracteres.
AI_MAX_ANSWER_CHARS = int(os.environ.get("AI_MAX_ANSWER_CHARS", "900"))
AI_MAX_INPUT_CHARS = int(os.environ.get("AI_MAX_INPUT_CHARS", "14000"))
# Topes de gasto en USD. Al alcanzarlos se cae al motor local en vez de gastar.
AI_PRESUPUESTO_USD = float(os.environ.get("AI_PRESUPUESTO_USD", "20"))
AI_LIMITE_USUARIO_USD = float(os.environ.get("AI_LIMITE_USUARIO_USD", "0.50"))

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend" if os.environ.get("EMAIL_HOST")
    else "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.resend.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "resend")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 15
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Onto <no-reply@onto.xz.com.ar>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
