"""Limpia el material viejo del volumen de medios.

Regla: el clip fuente se borra a los 30 días de publicado, porque el MP4 es lo que
se sirve. El MP4 se conserva 90 días: después ya vive en Instagram y solo ocupa
espacio. Las imágenes de las tarjetas no se tocan, porque son la miniatura de la
publicación y pesan poco.

    manage.py limpiar_media --dias-clip 30 --dias-render 90 --simular
"""
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from web.models import Publicacion


class Command(BaseCommand):
    help = "Borra clips y reels viejos del volumen de medios."

    def add_arguments(self, parser):
        parser.add_argument("--dias-clip", type=int, default=30)
        parser.add_argument("--dias-render", type=int, default=90)
        parser.add_argument("--simular", action="store_true", help="Muestra qué borraría.")
        parser.add_argument("--incluir-huerfanos", action="store_true",
                            help="Borra también archivos de medios sin borrador asociado.")

    def handle(self, *args, **opciones):
        media = Path(settings.MEDIA_ROOT)
        ahora = timezone.now()
        limite_clip = ahora - timedelta(days=opciones["dias_clip"])
        limite_video = ahora - timedelta(days=opciones["dias_render"])
        borrados = 0
        liberado = 0

        for publicacion in Publicacion.objects.exclude(estado="borrador"):
            publicado = publicacion.publicada_en or publicacion.actualizado

            if publicacion.clip_archivo and publicado < limite_clip:
                ruta = media / publicacion.clip_archivo
                if ruta.exists():
                    tamano = ruta.stat().st_size
                    if opciones["simular"]:
                        self.stdout.write(f"[simular] clip {ruta.name} ({tamano // 1024} KB)")
                    else:
                        ruta.unlink(missing_ok=True)
                        publicacion.clip_archivo = ""
                        publicacion.save(update_fields=["clip_archivo", "actualizado"])
                        self.stdout.write(f"clip borrado: {ruta.name}")
                    borrados += 1
                    liberado += tamano

            if publicacion.video and publicado < limite_video:
                ruta = media / publicacion.video
                if ruta.exists():
                    tamano = ruta.stat().st_size
                    if opciones["simular"]:
                        self.stdout.write(f"[simular] video {ruta.name} ({tamano // 1024} KB)")
                    else:
                        ruta.unlink(missing_ok=True)
                        self.stdout.write(f"video borrado: {ruta.name}")
                    borrados += 1
                    liberado += tamano

        if opciones["incluir_huerfanos"]:
            conocidos = {p.clip_archivo for p in Publicacion.objects.all() if p.clip_archivo}
            conocidos |= {p.video for p in Publicacion.objects.all() if p.video}
            for carpeta in ("stock", "publicaciones"):
                for archivo in (media / carpeta).glob("*"):
                    if archivo.is_file() and archivo.suffix in (".mp4", ".jpg"):
                        relativo = f"{carpeta}/{archivo.name}"
                        if relativo in conocidos:
                            continue
                        if archivo.stat().st_mtime > limite_clip.timestamp():
                            continue
                        tamano = archivo.stat().st_size
                        if opciones["simular"]:
                            self.stdout.write(f"[simular] huérfano {relativo} ({tamano // 1024} KB)")
                        else:
                            archivo.unlink(missing_ok=True)
                            self.stdout.write(f"huérfano borrado: {relativo}")
                        borrados += 1
                        liberado += tamano

        verbo = "se borrarían" if opciones["simular"] else "borrados"
        self.stdout.write(self.style.SUCCESS(
            f"{borrados} archivo(s) {verbo} · {liberado / 1024 / 1024:.1f} MB liberados"))
