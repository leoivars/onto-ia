"""Procesa los informes en cola cuando el motor de IA vuelve a estar disponible."""
from django.core.management.base import BaseCommand

from reports import cola


class Command(BaseCommand):
    help = "Reintenta generar los informes que quedaron en cola por falta de créditos."

    def add_arguments(self, parser):
        parser.add_argument("--limite", type=int, default=5)

    def handle(self, *args, **opciones):
        generados, restantes, motivo = cola.procesar(opciones["limite"])
        if generados:
            self.stdout.write(self.style.SUCCESS(f"Informes generados desde la cola: {generados}."))
        if restantes:
            self.stdout.write(self.style.WARNING(
                f"Siguen en cola: {restantes}." + (f" Motivo: {motivo}" if motivo else "")))
        elif generados:
            self.stdout.write("Cola vacía.")
