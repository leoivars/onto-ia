"""robots.txt y sitemap.xml sin depender del framework de sites."""
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

PRIVADAS = [
    "/panel/", "/cuenta/", "/informes/", "/entrevista/",
    "/ingresar/", "/registro/",
]


@require_GET
def robots(request):
    lineas = ["User-agent: *", "Allow: /", "Disallow: /admin/"]
    lineas += [f"Disallow: {ruta}" for ruta in PRIVADAS]
    lineas += ["", f"Sitemap: https://{settings.SITE_DOMAIN}/sitemap.xml"]
    return HttpResponse("\n".join(lineas) + "\n", content_type="text/plain; charset=utf-8")


@require_GET
def sitemap(request):
    base = f"https://{settings.SITE_DOMAIN}"
    hoy = timezone.localdate().isoformat()
    paginas = [("/", "1.0", "weekly"), ("/diagnostico/", "0.9", "monthly"),
               ("/precios/", "0.8", "monthly"), ("/legal/", "0.3", "yearly")]
    partes = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for ruta, prioridad, frecuencia in paginas:
        partes += [
            "  <url>",
            f"    <loc>{base}{ruta}</loc>",
            f"    <lastmod>{hoy}</lastmod>",
            f"    <changefreq>{frecuencia}</changefreq>",
            f"    <priority>{prioridad}</priority>",
            "  </url>",
        ]
    partes.append("</urlset>")
    return HttpResponse("\n".join(partes), content_type="application/xml; charset=utf-8")
