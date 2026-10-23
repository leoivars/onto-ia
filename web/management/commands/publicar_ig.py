"""Publica una tarjeta en Instagram: genera la imagen, la expone y la sube por API."""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from web import instagram
from web.tarjetas import tarjeta

NOMBRE_VALIDO = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


class Command(BaseCommand):
    help = "Genera una tarjeta y la publica en la cuenta de Instagram de Onto."

    def add_arguments(self, parser):
        parser.add_argument("--texto", required=True, help="Titular de la tarjeta.")
        parser.add_argument("--caption", default="", help="Texto de la publicación.")
        parser.add_argument("--nombre", required=True, help="Nombre del archivo, sin extensión.")
        parser.add_argument("--pie", default="Coaching ontológico con IA · onto.xz.com.ar")
        parser.add_argument("--solo-imagen", action="store_true",
                            help="Genera la imagen y no publica.")
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría.")

    def handle(self, *args, **opciones):
        nombre = opciones["nombre"].strip().lower()
        if not NOMBRE_VALIDO.match(nombre):
            raise CommandError("El nombre solo admite minúsculas, números y guiones.")

        salida = Path(settings.MEDIA_ROOT) / "publicaciones" / f"{nombre}.jpg"
        tarjeta(opciones["texto"], salida, pie=opciones["pie"])
        self.stdout.write(f"Imagen: {salida} ({salida.stat().st_size} bytes)")

        if opciones["solo_imagen"]:
            return

        url = f"https://{settings.SITE_DOMAIN}/ig/{nombre}.jpg"
        self.stdout.write(f"URL pública: {url}")
        if opciones["dry_run"]:
            return

        contenedor = instagram.crear_contenedor(url, opciones["caption"])
        self.stdout.write(f"Contenedor: {contenedor}")
        instagram.esperar_listo(contenedor)
        media_id = instagram.publicar(contenedor)
        datos = instagram.datos_publicacion(media_id)
        self.stdout.write(self.style.SUCCESS(
            f"Publicado {media_id} · {datos.get('permalink')}"))
