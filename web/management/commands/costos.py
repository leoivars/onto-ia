"""Consumo de IA por día y por usuario.

    python manage.py costos
    python manage.py costos --dias 30
    python manage.py costos --usuario mariana@ejemplo.com
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from reports.models import Report


class Command(BaseCommand):
    help = "Muestra el costo de IA por día y por usuario."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=7)
        parser.add_argument("--usuario", type=str, default="")

    def handle(self, *args, **opciones):
        desde = timezone.now() - timedelta(days=opciones["dias"])
        informes = Report.objects.filter(engine="ia", created_at__gte=desde)
        if opciones["usuario"]:
            informes = informes.filter(user__email__icontains=opciones["usuario"])

        if not informes.exists():
            self.stdout.write("Sin informes con IA en el período.")
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Período: últimos {opciones['dias']} días"))

        por_dia = (informes.annotate(dia=TruncDate("created_at")).values("dia")
                   .annotate(informes=Count("id"), entrada=Sum("tokens_in"),
                             cache=Sum("tokens_cache"), salida=Sum("tokens_out"),
                             costo=Sum("costo_usd")).order_by("-dia"))
        total = 0.0
        self.stdout.write("\nDía        Informes  Entrada   Caché    Salida   Costo USD")
        for fila in por_dia:
            total += float(fila["costo"] or 0)
            self.stdout.write(
                f"{fila['dia']}  {fila['informes']:>8}  {fila['entrada'] or 0:>7}  "
                f"{fila['cache'] or 0:>6}  {fila['salida'] or 0:>7}   {float(fila['costo'] or 0):.5f}")

        por_usuario = (informes.values("user__email")
                       .annotate(informes=Count("id"), costo=Sum("costo_usd"),
                                 entrada=Sum("tokens_in")).order_by("-costo"))
        self.stdout.write("\nCuenta                          Informes   Entrada   Costo USD")
        for fila in por_usuario:
            self.stdout.write(
                f"{fila['user__email'][:30]:30}  {fila['informes']:>8}  {fila['entrada'] or 0:>8}   "
                f"{float(fila['costo'] or 0):.5f}")

        self.stdout.write(self.style.SUCCESS(f"\nTotal del período: US$ {total:.5f}"))
