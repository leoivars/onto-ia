"""Pixabay: búsqueda y descarga de clips y fotos para las piezas de Onto.

Licencia (Pixabay Content License): uso comercial permitido, sin necesidad de
atribución, pero no se puede redistribuir el archivo original tal cual ni
sugerir que las personas retratadas avalan el producto. Por eso se eligen planos
sin caras identificables y siempre se interviene la imagen (color, texto, recorte).

La clave va en el .env del servidor como PIXABAY_API_KEY. Nunca en el código.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings


class PixabayError(Exception):
    pass


def configurado():
    return bool(getattr(settings, "PIXABAY_API_KEY", ""))


def _get(url, timeout=30):
    pedido = urllib.request.Request(url, method="GET")
    pedido.add_header("User-Agent", "Onto/1.0 (+https://onto.xz.com.ar)")
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
            return json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detalle = ""
        try:
            detalle = exc.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        if exc.code == 429:
            raise PixabayError("límite de consultas alcanzado (100 por minuto)") from exc
        if exc.code == 400:
            raise PixabayError(f"consulta rechazada: {detalle}") from exc
        raise PixabayError(f"error {exc.code}: {detalle}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PixabayError(str(exc)) from exc


def _base(recurso=""):
    """URL del recurso: sin argumento apunta a fotos, con «videos» al de clips."""
    if not configurado():
        raise PixabayError("falta PIXABAY_API_KEY en el .env del servidor")
    raiz = settings.PIXABAY_API.rstrip("/") + "/"
    return raiz + (f"{recurso}/" if recurso else "")


def buscar_videos(consulta, limite=20, vertical=True, orden="popular", duracion=None):
    """Clips de video. Devuelve una lista normalizada, ya filtrada por tamaño vertical."""
    parametros = {
        "key": settings.PIXABAY_API_KEY,
        "q": consulta,
        "per_page": min(int(limite), 200),
        "order": orden,
        "safesearch": "true",
        "video_type": "film",
    }
    if vertical:
        parametros["orientation"] = "vertical"
    if duracion:
        parametros["min_duration"] = duracion[0]
        parametros["max_duration"] = duracion[1]

    datos = _get(_base("videos") + "?" + urllib.parse.urlencode(parametros))
    clips = []
    for hit in datos.get("hits", []):
        variantes = hit.get("videos") or {}
        disponibles = []
        for nombre in ("large", "medium", "small", "tiny"):
            v = variantes.get(nombre) or {}
            if v.get("url"):
                disponibles.append({
                    "url": v["url"],
                    "ancho": int(v.get("width") or 0),
                    "alto": int(v.get("height") or 0),
                    "bytes": int(v.get("size") or 0),
                    "calidad": nombre,
                })
        if not disponibles:
            continue
        # La mejor variante es la de mayor superficie, no la última de la lista.
        mejor = max(disponibles, key=lambda v: v["ancho"] * v["alto"])
        clips.append({
            "id": hit.get("id"),
            "tipo": "video",
            "etiquetas": hit.get("tags", ""),
            "duracion": int(hit.get("duration") or 0),
            "ancho": mejor["ancho"],
            "alto": mejor["alto"],
            "archivo": mejor["url"],
            "calidad": mejor["calidad"],
            "bytes": mejor["bytes"],
            "autor": hit.get("user", ""),
            "pagina": hit.get("pageURL", ""),
        })
    return clips


def buscar_fotos(consulta, limite=20, vertical=True, orden="popular"):
    parametros = {
        "key": settings.PIXABAY_API_KEY,
        "q": consulta,
        "per_page": min(int(limite), 200),
        "order": orden,
        "image_type": "photo",
        "safesearch": "true",
    }
    if vertical:
        parametros["orientation"] = "vertical"

    datos = _get(_base() + "?" + urllib.parse.urlencode(parametros))
    fotos = []
    for hit in datos.get("hits", []):
        fotos.append({
            "id": hit.get("id"),
            "tipo": "foto",
            "etiquetas": hit.get("tags", ""),
            "ancho": int(hit.get("imageWidth") or 0),
            "alto": int(hit.get("imageHeight") or 0),
            "archivo": hit.get("largeImageURL") or hit.get("webformatURL", ""),
            "autor": hit.get("user", ""),
            "pagina": hit.get("pageURL", ""),
        })
    return fotos


def elegir(recursos, minimo_alto=1280, duracion=(4, 20)):
    """Elige el mejor recurso para un reel 1080x1920.

    Regla: se prefieren los verticales. Un horizontal solo sirve si es 4K, porque
    al recortarlo a 9:16 quedan 1215x2160 y sobra resolución; con 1080p el recorte
    daría 607 de ancho y habría que inventar píxeles.
    """
    candidatos = []
    for r in recursos:
        relacion = r["ancho"] / r["alto"] if r["alto"] else 0
        vertical = relacion <= 0.8
        if vertical:
            if r["alto"] < minimo_alto or r["ancho"] < 720:
                continue
            modo = "vertical"
        else:
            if r["alto"] < 2160:  # horizontal: solo si es 4K
                continue
            modo = "recorte"
        if r["tipo"] == "video" and not (duracion[0] <= r["duracion"] <= duracion[1]):
            continue
        candidatos.append({**r, "modo": modo})
    if not candidatos:
        return None
    # Primero los verticales, después los de mayor resolución.
    candidatos.sort(key=lambda r: (r["modo"] == "vertical", r["alto"] * r["ancho"]))
    return candidatos[-1]


def descargar(recurso, destino, maximo_bytes=80 * 1024 * 1024):
    """Baja el archivo a disco. Devuelve la ruta."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    pedido = urllib.request.Request(recurso["archivo"], method="GET")
    pedido.add_header("User-Agent", "Onto/1.0 (+https://onto.xz.com.ar)")
    try:
        with urllib.request.urlopen(pedido, timeout=120) as respuesta:
            total = 0
            with open(destino, "wb") as salida:
                while True:
                    bloque = respuesta.read(256 * 1024)
                    if not bloque:
                        break
                    total += len(bloque)
                    if total > maximo_bytes:
                        raise PixabayError("el archivo supera el tamaño máximo permitido")
                    salida.write(bloque)
    except urllib.error.HTTPError as exc:
        raise PixabayError(f"no se pudo descargar ({exc.code})") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise PixabayError(f"no se pudo descargar: {exc}") from exc
    if destino.stat().st_size < 10_000:
        destino.unlink(missing_ok=True)
        raise PixabayError("el archivo bajó incompleto")
    return destino


def credito(recurso):
    """Texto de crédito. La licencia no lo exige; se guarda para trazabilidad."""
    return f"{recurso.get('etiquetas', '')[:60]} · Pixabay · {recurso.get('autor', '')}"
