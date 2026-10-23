"""Cola de publicaciones: se generan como borrador y se publican solo al aprobarlas."""
import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from . import instagram
from .models import Publicacion
from .tarjetas import tarjeta

logger = logging.getLogger(__name__)


def generar(nombre, texto, caption="", pie=None, programada=None):
    """Crea el borrador y dibuja la imagen. No publica nada."""
    publicacion, creada = Publicacion.objects.get_or_create(
        nombre=nombre,
        defaults={"texto": texto, "caption": caption,
                  "pie": pie or "Coaching ontológico con IA · onto.xz.com.ar",
                  "programada": programada})
    salida = Path(settings.MEDIA_ROOT) / "publicaciones" / f"{nombre}.jpg"
    tarjeta(publicacion.texto, salida, pie=publicacion.pie)
    return publicacion, creada


def programar(publicacion, dias=1):
    """La aprueba y la deja para dentro de N días, a las 10 de la mañana."""
    from datetime import datetime, time

    base = timezone.localdate() + timedelta(days=dias)
    publicacion.estado = "aprobada"
    publicacion.programada = timezone.make_aware(datetime.combine(base, time(10, 0)))
    publicacion.save(update_fields=["estado", "programada", "actualizado"])
    return publicacion


def publicar(publicacion):
    """Publica ahora. Deja el estado y el error registrados."""
    if publicacion.estado == "publicada":
        return publicacion
    try:
        contenedor = instagram.crear_contenedor(publicacion.imagen_url, publicacion.caption)
        instagram.esperar_listo(contenedor)
        media_id = instagram.publicar(contenedor)
        datos = instagram.datos_publicacion(media_id)
        publicacion.ig_id = media_id
        publicacion.permalink = datos.get("permalink", "")
        publicacion.estado = "publicada"
        publicacion.publicada_en = timezone.now()
        publicacion.error = ""
    except instagram.InstagramError as exc:
        publicacion.estado = "error"
        publicacion.error = str(exc)[:500]
        logger.warning("No se pudo publicar %s: %s", publicacion.nombre, exc)
    publicacion.save()
    return publicacion


def publicar_vencidas(limite=3):
    ahora = timezone.now()
    pendientes = Publicacion.objects.filter(
        estado="aprobada", programada__lte=ahora).order_by("programada")[:limite]
    publicadas = 0
    for publicacion in pendientes:
        publicar(publicacion)
        publicadas += int(publicacion.estado == "publicada")
    return publicadas
