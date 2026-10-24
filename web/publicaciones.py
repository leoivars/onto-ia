"""Cola de publicaciones: se generan como borrador y se publican solo al aprobarlas."""
import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from . import instagram, stock
from .models import Publicacion
from .tarjetas import tarjeta

logger = logging.getLogger(__name__)

# Temas de las piezas → búsqueda en inglés, porque el índice de Pixabay lo está.
CONSULTAS = [
    (("reproche", "pedido", "conversación", "conversacion", "decir"),
     "writing notebook hand"),
    (("promesa", "compromiso", "cumplir", "aviso"),
     "calendar planning desk"),
    (("juicio", "hecho", "conclusión", "conclusion", "interpretación"),
     "fountain pen paper close up"),
    (("miedo", "riesgo", "crisis", "ansiedad"),
     "quiet window morning light"),
    (("trabajo", "jefe", "equipo", "reunión", "reunion"),
     "office desk laptop sunlight"),
]
CONSULTA_BASE = "writing notebook desk"


def consulta_para(texto):
    """Elige la búsqueda según el tema del texto. Siempre devuelve algo."""
    minusculas = (texto or "").lower()
    for palabras, consulta in CONSULTAS:
        if any(p in minusculas for p in palabras):
            return consulta
    return CONSULTA_BASE


def agregar_clip(publicacion, limite=25):
    """Busca y baja el clip del borrador. Si no hay clave o no hay resultados, sigue sin clip."""
    if not stock.configurado():
        logger.info("Sin PIXABAY_API_KEY: %s queda sin clip", publicacion.nombre)
        return False
    consulta = publicacion.consulta or consulta_para(publicacion.texto)
    publicacion.consulta = consulta
    try:
        recursos = stock.buscar_videos(consulta, limite=limite)
        elegido = stock.elegir(recursos)
        if not elegido:
            recursos = stock.buscar_videos(consulta, limite=limite, vertical=False)
            elegido = stock.elegir(recursos)
        if not elegido:
            logger.info("Sin clip para %s (%s)", publicacion.nombre, consulta)
            publicacion.save(update_fields=["consulta", "actualizado"])
            return False
        extension = "mp4" if elegido["tipo"] == "video" else "jpg"
        destino = Path(settings.MEDIA_ROOT) / "stock" / f"{publicacion.nombre}.{extension}"
        stock.descargar(elegido, destino)
        publicacion.clip_id = str(elegido["id"])
        publicacion.clip_archivo = f"stock/{publicacion.nombre}.{extension}"
        publicacion.clip_autor = elegido.get("autor", "")[:80]
        publicacion.clip_modo = elegido.get("modo", "vertical")
        publicacion.save(update_fields=["consulta", "clip_id", "clip_archivo", "clip_autor",
                                        "clip_modo", "actualizado"])
        return True
    except stock.PixabayError as exc:
        logger.warning("Pixabay no devolvió clip para %s: %s", publicacion.nombre, exc)
        publicacion.save(update_fields=["consulta", "actualizado"])
        return False


def generar(nombre, texto, caption="", pie=None, programada=None, fondo=None, formato="tarjeta"):
    """Crea el borrador, dibuja la portada y, si es reel, le busca su clip. No publica nada."""
    publicacion, creada = Publicacion.objects.get_or_create(
        nombre=nombre,
        defaults={"texto": texto, "caption": caption, "alt_texto": texto[:300],
                  "pie": pie or "Coaching ontológico · onto.xz.com.ar",
                  "formato": formato, "programada": programada,
                  "consulta": consulta_para(texto) if formato == "reel" else ""})
    salida = Path(settings.MEDIA_ROOT) / "publicaciones" / f"{nombre}.jpg"
    if fondo and Path(fondo).exists():
        from .tarjetas import tarjeta_foto

        tarjeta_foto(publicacion.texto, salida, fondo, pie=publicacion.pie)
    else:
        tarjeta(publicacion.texto, salida, pie=publicacion.pie)
    if publicacion.es_reel and not publicacion.clip_archivo:
        agregar_clip(publicacion)
    return publicacion, creada


def programar(publicacion, dias=1):
    """La aprueba y la deja para dentro de N días, a las 10 de la mañana."""
    from datetime import datetime, time

    base = timezone.localdate() + timedelta(days=dias)
    publicacion.estado = "aprobada"
    publicacion.programada = timezone.make_aware(datetime.combine(base, time(10, 0)))
    publicacion.save(update_fields=["estado", "programada", "actualizado"])
    return publicacion


def render(publicacion, segundos=None):
    """Genera el MP4 del reel: clip, texto al ritmo y, si hay proveedor, voz.

    Con voz, la duración la manda el audio: el texto se reparte sobre lo que dura la
    lectura. Sin voz, se usa el largo pedido (8 s por defecto).
    """
    from django.conf import settings as cfg

    from . import voz as voz_api
    from .video import reel_clip

    if not publicacion.es_reel:
        return None
    if not publicacion.clip_archivo:
        raise RuntimeError("el borrador no tiene clip")
    entrada = Path(cfg.MEDIA_ROOT) / publicacion.clip_archivo
    if not entrada.exists():
        raise RuntimeError(f"falta el archivo del clip: {entrada}")

    audio = None
    entradas = list(publicacion.tiempos or [])
    guion = (publicacion.guion or publicacion.texto or "").strip()

    if voz_api.disponible() and guion:
        destino_audio = Path(cfg.MEDIA_ROOT) / "voz" / f"{publicacion.nombre}.mp3"
        voz_api.generar(guion, destino_audio)
        audio = destino_audio
        duracion = voz_api.duracion(destino_audio)
        segundos = round(duracion + 0.8, 2)
        # Si los tiempos no fueron medidos sobre una música, se reparten sobre la voz.
        if not entradas:
            # Un bloque de texto por frase del titular: entran cuando la voz ya dijo lo anterior.
            import re as _re

            frases = [f for f in _re.split(r"(?<=[.!?…])\s+", publicacion.texto or "") if f.strip()]
            entradas = voz_api.repartir(duracion, max(len(frases), 2))
            publicacion.tiempos = entradas
            publicacion.save(update_fields=["tiempos", "actualizado"])

    segundos = segundos or 8
    salida = Path(cfg.MEDIA_ROOT) / "publicaciones" / f"{publicacion.nombre}.mp4"
    reel_clip(entrada, publicacion.texto, salida, segundos=segundos,
              recorte=publicacion.clip_modo == "recorte",
              entradas=entradas, audio=audio)
    publicacion.video = f"publicaciones/{publicacion.nombre}.mp4"
    publicacion.save(update_fields=["video", "actualizado"])
    return salida


def publicar(publicacion):
    """Publica ahora. Deja el estado y el error registrados."""
    if publicacion.estado == "publicada":
        return publicacion
    try:
        if publicacion.es_reel:
            if not publicacion.tiene_video:
                render(publicacion)
            contenedor = instagram.crear_contenedor_reel(
                publicacion.video_url, publicacion.caption,
                alt_texto=publicacion.alt_texto or "")
            instagram.esperar_listo(contenedor, intentos=60, pausa=5)
            media_id = instagram.publicar(contenedor)
            datos = instagram.datos_publicacion(media_id)
            publicacion.ig_id = media_id
            publicacion.permalink = datos.get("permalink", "")
            publicacion.estado = "publicada"
            publicacion.publicada_en = timezone.now()
            publicacion.error = ""
            publicacion.save()
            return publicacion
        alt = publicacion.alt_texto or f"Tarjeta de Onto: {publicacion.texto}"
        contenedor = instagram.crear_contenedor(publicacion.imagen_url, publicacion.caption,
                                                alt_texto=alt)
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
