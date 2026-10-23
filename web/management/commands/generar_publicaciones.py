"""Genera los borradores de una tanda de tarjetas. No publica nada."""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from web.publicaciones import generar


class Command(BaseCommand):
    help = "Crea borradores de publicaciones a partir de un archivo JSON."

    def add_arguments(self, parser):
        parser.add_argument("archivo", help="JSON con una lista de {nombre, texto, caption}.")

    def handle(self, *args, **opciones):
        ruta = Path(opciones["archivo"])
        if not ruta.exists():
            raise CommandError(f"No existe {ruta}")
        entradas = json.loads(ruta.read_text(encoding="utf-8"))
        creadas = actualizadas = 0
        for entrada in entradas:
            _, nueva = generar(
                nombre=entrada["nombre"],
                texto=entrada["texto"],
                caption=entrada.get("caption", ""),
                pie=entrada.get("pie"))
            creadas += int(nueva)
            actualizadas += int(not nueva)
        self.stdout.write(self.style.SUCCESS(
            f"Borradores: {creadas} nuevos, {actualizadas} actualizados. Nada publicado."))
