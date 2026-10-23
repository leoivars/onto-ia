"""Política de retención: borra lo que ya no hace falta.

Los diagnósticos públicos se conservan 12 meses; los correos captados en la landing, 24 meses.
Se ejecuta a mano o por cron. Con --dry-run informa sin borrar.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from diagnostico.models import Diagnostico
from web.models import Lead, Visita


class Command(BaseCommand):
    help = "Purga diagnósticos y leads vencidos según la política de retención."

    def add_arguments(self, parser):
        parser.add_argument("--dias-diagnostico", type=int, default=365)
        parser.add_argument("--dias-lead", type=int, default=730)
        parser.add_argument("--dias-visita", type=int, default=90)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opciones):
        ahora = timezone.now()
        corte_diag = ahora - timedelta(days=opciones["dias_diagnostico"])
        corte_lead = ahora - timedelta(days=opciones["dias_lead"])
        corte_visita = ahora - timedelta(days=opciones["dias_visita"])

        diag = Diagnostico.objects.filter(created_at__lt=corte_diag)
        leads = Lead.objects.filter(created_at__lt=corte_lead)
        visitas = Visita.objects.filter(creada__lt=corte_visita)
        if opciones["dry_run"]:
            self.stdout.write(f"[dry-run] diagnósticos a borrar: {diag.count()}")
            self.stdout.write(f"[dry-run] leads a borrar: {leads.count()}")
            self.stdout.write(f"[dry-run] visitas a borrar: {visitas.count()}")
            return

        n_diag, _ = diag.delete()
        n_leads, _ = leads.delete()
        # Antes de borrar el detalle, se guarda el agregado del día: la serie histórica queda.
        from web.agregados import agregar_dia

        for fecha in visitas.values_list("creada__date", flat=True).distinct():
            agregar_dia(fecha)
        n_visitas, _ = visitas.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Borrados {n_diag} diagnósticos, {n_leads} leads y {n_visitas} visitas vencidas."))
