"""Trae las métricas de las publicaciones de Instagram y las guarda."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from web import analitica_ig, instagram
from web.models import Publicacion


class Command(BaseCommand):
    help = "Lee alcance, guardados y comentarios de lo publicado y guarda una foto del momento."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=90)

    def handle(self, *args, **opciones):
        desde = timezone.now() - timedelta(days=opciones["dias"])
        publicaciones = Publicacion.objects.filter(
            estado="publicada", publicada_en__gte=desde).exclude(ig_id="")

        leidas = fallidas = 0
        for publicacion in publicaciones:
            try:
                analitica_ig.actualizar(publicacion)
                leidas += 1
            except instagram.InstagramError as exc:
                fallidas += 1
                self.stdout.write(self.style.WARNING(
                    f"{publicacion.nombre}: {exc}"))

        self.stdout.write(self.style.SUCCESS(
            f"Métricas leídas: {leidas}. Con error: {fallidas}."))
