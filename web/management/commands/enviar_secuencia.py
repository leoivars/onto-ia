"""Envía los correos de la secuencia que ya vencieron."""
from django.core.management.base import BaseCommand

from web.correos import enviar_pendientes


class Command(BaseCommand):
    help = "Envía los correos de seguimiento programados y vencidos."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=200)

    def handle(self, *args, **opciones):
        enviados, omitidos, fallidos = enviar_pendientes(opciones["limite"])
        self.stdout.write(
            f"Secuencia: {enviados} enviados, {omitidos} omitidos, {fallidos} fallidos.")
