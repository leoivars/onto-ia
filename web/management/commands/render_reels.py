"""Renderiza los reels pendientes de la cola.

Corre por cron, no dentro de un pedido web: ffmpeg tarda unos veinte segundos por
pieza y bloquearía a los usuarios.

    manage.py render_reels --limite 3
"""
from django.core.management.base import BaseCommand

from web import publicaciones as cola
from web.models import Publicacion


class Command(BaseCommand):
    help = "Genera el MP4 de los reels aprobados o en borrador que todavía no lo tienen."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=5)
        parser.add_argument("--segundos", type=int, default=8)
        parser.add_argument("--todos", action="store_true",
                            help="Incluye también los ya publicados sin video.")

    def handle(self, *args, **opciones):
        estados = ["aprobada", "borrador"] + (["publicada"] if opciones["todos"] else [])
        pendientes = (Publicacion.objects
                      .filter(formato="reel", estado__in=estados, video="")
                      .order_by("creado")[:opciones["limite"]])
        if not pendientes:
            self.stdout.write("No hay reels pendientes de render.")
            return

        for publicacion in pendientes:
            if not publicacion.clip_archivo:
                self.stdout.write(self.style.WARNING(
                    f"{publicacion.nombre}: sin clip, se saltea."))
                continue
            try:
                ruta = cola.render(publicacion, segundos=opciones["segundos"])
                self.stdout.write(self.style.SUCCESS(
                    f"{publicacion.nombre}: {ruta.name} ({ruta.stat().st_size // 1024} KB)"))
            except Exception as exc:  # un reel que falla no debe frenar la cola
                self.stdout.write(self.style.ERROR(f"{publicacion.nombre}: {exc}"))
