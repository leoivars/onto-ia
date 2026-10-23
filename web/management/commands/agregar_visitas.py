"""Agrega las visitas del día en resúmenes que se conservan sin datos personales."""
from django.core.management.base import BaseCommand

from web.agregados import agregar_pendientes, agregar_rango


class Command(BaseCommand):
    help = "Recalcula los resúmenes diarios de visitas."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=3,
                            help="Cantidad de días hacia atrás a recalcular.")

    def handle(self, *args, **opciones):
        filas = agregar_pendientes(opciones["dias"])
        self.stdout.write(self.style.SUCCESS(f"Resúmenes actualizados: {filas} filas."))
