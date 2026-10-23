"""Publica lo que fue aprobado y ya llegó su día."""
from django.core.management.base import BaseCommand

from web.publicaciones import publicar_vencidas


class Command(BaseCommand):
    help = "Publica las tarjetas aprobadas cuya fecha ya venció."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=3)

    def handle(self, *args, **opciones):
        n = publicar_vencidas(opciones["limite"])
        self.stdout.write(f"Publicadas: {n}.")
