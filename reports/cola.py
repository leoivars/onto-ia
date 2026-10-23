"""Cola de informes cuando la IA no tiene saldo.

El pedido no se pierde ni se reemplaza por un informe de plantilla: queda en cola, el usuario
recibe un correo, y un cron reintenta hasta que el proveedor vuelve a responder.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from . import ai, engine
from .models import InformeEnCola

logger = logging.getLogger(__name__)


def _enlace_informe(report):
    return f"https://{settings.SITE_DOMAIN}/informes/{report.pk}/"


def _avisar_cola(cola):
    try:
        send_mail(
            "Su informe quedó en cola · Onto",
            (
                "Recibimos su pedido de informe y quedó en cola.\n\n"
                "En este momento estamos con un problema técnico en el motor de escritura y no "
                "podemos generarlo. Ya estamos trabajando para resolverlo. No hace falta que "
                "vuelva a pedirlo: lo generamos apenas se restablezca y le avisamos por este "
                "mismo correo.\n\n"
                f"Si quiere ver el estado, entre a https://{settings.SITE_DOMAIN}/panel/\n\n"
                "—\nOnto · Coaching ontológico"
            ),
            None, [cola.user.email], fail_silently=True)
    except Exception:
        logger.exception("No se pudo avisar la cola a %s", cola.user.email)


def _avisar_listo(cola):
    try:
        send_mail(
            "Su informe está listo · Onto",
            (
                f"{cola.user.profile.nombre or ''} su informe ya está escrito.\n\n"
                f"Puede leerlo acá: {_enlace_informe(cola.report)}\n\n"
                "Gracias por la paciencia.\n\n"
                "—\nOnto · Coaching ontológico"
            ),
            None, [cola.user.email], fail_silently=True)
    except Exception:
        logger.exception("No se pudo avisar el informe listo a %s", cola.user.email)


def encolar(user, motivo=""):
    """Pone el pedido en cola. Si ya había uno pendiente, lo reutiliza."""
    cola = InformeEnCola.objects.filter(user=user, estado="pendiente").first()
    creada = False
    if not cola:
        cola = InformeEnCola.objects.create(user=user, motivo=motivo[:500])
        creada = True
        _avisar_cola(cola)
        logger.warning("Informe en cola para %s: %s", user.pk, motivo[:120])
    return cola, creada


def pendientes():
    return InformeEnCola.objects.filter(estado="pendiente").order_by("creado")


def procesar(limite=5):
    """Intenta generar los informes en cola. Devuelve (generados, restantes, motivo).

    Si el proveedor sigue sin saldo, corta en el primero y no quema intentos en vano.
    """
    generados = 0
    for cola in list(pendientes()[:limite]):
        cola.intentos += 1
        try:
            report = engine.generar(cola.user)
            cola.report = report
            cola.estado = "listo"
            cola.procesado_en = timezone.now()
            cola.ultimo_error = ""
            cola.save(update_fields=["report", "estado", "procesado_en", "ultimo_error",
                                     "intentos"])
            _avisar_listo(cola)
            generados += 1
        except ai.SinCreditos as exc:
            cola.ultimo_error = str(exc)[:500]
            cola.save(update_fields=["intentos", "ultimo_error"])
            return generados, pendientes().count(), f"sin créditos: {exc}"[:200]
        except Exception as exc:
            cola.ultimo_error = str(exc)[:500]
            cola.save(update_fields=["intentos", "ultimo_error"])
            logger.exception("Error generando informe en cola para %s", cola.user_id)

    return generados, pendientes().count(), ""
