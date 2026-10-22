"""Saldo disponible en el proveedor de IA (DeepSeek).

    python manage.py saldo
"""
import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Consulta el saldo de crédito disponible en la API de IA."

    def handle(self, *args, **opciones):
        if not settings.AI_API_KEY:
            raise CommandError("Falta AI_API_KEY en el entorno.")

        req = urllib.request.Request(
            settings.AI_BASE_URL.rstrip("/") + "/user/balance",
            headers={"Authorization": f"Bearer {settings.AI_API_KEY.strip()}",
                     "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as respuesta:
                datos = json.loads(respuesta.read().decode())
        except urllib.error.HTTPError as exc:
            raise CommandError(
                f"El proveedor no expone el saldo por API (HTTP {exc.code}). "
                f"Consúltelo en el panel.") from exc
        except Exception as exc:
            raise CommandError(f"No se pudo consultar el saldo: {exc}") from exc

        disponible = datos.get("is_available")
        self.stdout.write(f"Proveedor: {settings.AI_BASE_URL}")
        self.stdout.write(f"Servicio disponible: {'sí' if disponible else 'no'}")
        for info in datos.get("balance_infos", []):
            self.stdout.write(self.style.SUCCESS(
                f"Saldo {info.get('currency')}: {info.get('total_balance')} "
                f"(recargado {info.get('topped_up_balance')}, "
                f"bonificado {info.get('granted_balance')})"))
