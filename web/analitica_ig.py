"""Lectura de métricas de Instagram y control de repetición del contenido."""
import re
import unicodedata

from . import instagram
from .models import MetricaPublicacion, Publicacion

VACIAS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "que", "y", "o", "en",
    "es", "son", "lo", "le", "se", "su", "sus", "por", "para", "con", "sin", "más", "mas", "no",
    "al", "a", "cómo", "como", "está", "esta", "está", "usted", "pero", "si", "ya",
}


def _tokens(texto):
    plano = "".join(c for c in unicodedata.normalize("NFD", (texto or "").lower())
                    if unicodedata.category(c) != "Mn")
    palabras = re.findall(r"[a-zñ]{3,}", plano)
    return {p for p in palabras if p not in VACIAS}


def similitud(a, b):
    """Jaccard sobre palabras significativas. 0 = nada en común, 1 = idéntico."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return round(len(ta & tb) / len(ta | tb), 2)


def parecido(publicacion):
    """La publicación más parecida ya publicada o en cola, con su porcentaje."""
    otras = Publicacion.objects.exclude(pk=publicacion.pk).exclude(estado="descartada")
    mejor, puntaje = None, 0.0
    for otra in otras:
        valor = similitud(publicacion.texto, otra.texto)
        if valor > puntaje:
            mejor, puntaje = otra, valor
    return mejor, puntaje


def actualizar(publicacion):
    """Trae las métricas de una publicación ya publicada y las guarda."""
    if not publicacion.ig_id:
        return None
    datos = instagram.insights(publicacion.ig_id)
    return MetricaPublicacion.objects.create(
        publicacion=publicacion,
        alcance=datos.get("reach", 0) or 0,
        impresiones=datos.get("impressions", 0) or 0,
        likes=datos.get("likes", 0) or 0,
        comentarios=datos.get("comments", 0) or 0,
        compartidos=datos.get("shares", 0) or 0,
        guardados=datos.get("saved", 0) or 0,
    )


def resumen():
    """Lo último medido por publicación, ordenado por guardados por mil de alcance."""
    ultimas = {}
    for metrica in MetricaPublicacion.objects.order_by("publicacion_id", "-medido"):
        ultimas.setdefault(metrica.publicacion_id, metrica)

    filas = sorted(
        ({"publicacion": m.publicacion, "metrica": m} for m in ultimas.values()),
        key=lambda f: f["metrica"].guardados_por_mil, reverse=True)

    total = len(filas)
    if not total:
        return {"filas": [], "lectura": "Todavía no hay métricas: se leen a partir del día siguiente "
                                       "de publicar."}

    mejor = filas[0]["metrica"]
    peor = filas[-1]["metrica"]
    lectura = (
        f"Lo que más se guardó: «{mejor.publicacion.texto[:60]}» con "
        f"{mejor.guardados_por_mil} guardados por mil de alcance. "
        f"Lo que menos: «{peor.publicacion.texto[:60]}» con {peor.guardados_por_mil}. "
        f"Guardar es la señal más fuerte: indica que la pieza le sirvió a alguien más tarde."
        if total > 1 else
        f"Una sola pieza medida ({mejor.guardados_por_mil} guardados por mil). Con tres o cuatro "
        f"se puede comparar y decidir qué línea repetir."
    )
    return {"filas": filas, "lectura": lectura}
