"""Medición propia, sin cookies de terceros ni datos personales.

Registra visitas a páginas públicas y guarda el origen (UTM o referente) en la sesión para
poder atribuir después el diagnóstico y el registro. No guarda IP ni user agent.
"""
import hashlib
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

EXCLUIDOS = (
    "/admin", "/static", "/media", "/metricas", "/panel", "/cuenta", "/entrevista",
    "/informes", "/e/", "/favicon", "/robots.txt", "/sitemap.xml", "/baja/",
)

MAPA_REFERENTES = {
    "instagram.com": "instagram",
    "l.instagram.com": "instagram",
    "facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "t.co": "x",
    "x.com": "x",
    "twitter.com": "x",
    "linkedin.com": "linkedin",
    "lnkd.in": "linkedin",
    "google.com": "google",
    "google.com.ar": "google",
    "bing.com": "bing",
    "whatsapp.com": "whatsapp",
    "wa.me": "whatsapp",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "reddit.com": "reddit",
}


def _host(referente):
    try:
        return (urlparse(referente).hostname or "").replace("www.", "")
    except Exception:
        return ""


def origen_de(request):
    """Devuelve el origen de la visita y lo deja fijado en la sesión (primer toque)."""
    if not hasattr(request, "session"):
        return ""
    fijado = request.session.get("origen")
    if fijado:
        return fijado

    fuente = (request.GET.get("utm_source") or "").strip().lower()[:60]
    medio = (request.GET.get("utm_medium") or "").strip().lower()[:60]
    campana = (request.GET.get("utm_campaign") or "").strip().lower()[:60]

    if fuente:
        origen = f"{fuente}/{medio}" if medio else fuente
    else:
        host = _host(request.META.get("HTTP_REFERER", ""))
        origen = next((v for k, v in MAPA_REFERENTES.items() if host.endswith(k)), "") or (
            host[:60] if host else "directo")

    request.session["origen"] = origen
    request.session["utm_fuente"] = fuente
    request.session["utm_medio"] = medio
    request.session["utm_campana"] = campana
    return origen


def _sesion_hash(request):
    clave = request.session.session_key or ""
    if not clave:
        request.session.save()
        clave = request.session.session_key or ""
    return hashlib.sha256(clave.encode()).hexdigest()[:32]


class VisitasMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._registrar(request, response)
        except Exception:
            logger.exception("No se pudo registrar la visita")
        return response

    def _registrar(self, request, response):
        from .models import Visita

        if request.method != "GET" or response.status_code != 200:
            return
        if "text/html" not in response.get("Content-Type", ""):
            return
        if any(request.path.startswith(p) for p in EXCLUIDOS):
            return

        origen = origen_de(request)
        Visita.objects.create(
            ruta=request.path[:120],
            referente=request.META.get("HTTP_REFERER", "")[:200],
            origen=(origen or "")[:60],
            fuente=(request.session.get("utm_fuente") or "")[:60],
            medio=(request.session.get("utm_medio") or "")[:60],
            campana=(request.session.get("utm_campana") or "")[:60],
            sesion=_sesion_hash(request),
            usuario=request.user if getattr(request, "user", None) and
            request.user.is_authenticated else None,
        )
