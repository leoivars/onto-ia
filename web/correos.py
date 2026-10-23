"""Programación y envío de la secuencia posterior al diagnóstico."""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone

from .models import EmailSecuencia, OptOut
from .secuencia import DIAS, PASOS

logger = logging.getLogger(__name__)


def programar(email):
    """Agenda los cuatro correos. Idempotente: no duplica pasos ya agendados."""
    email = (email or "").strip().lower()
    if not email:
        return 0
    ahora = timezone.now()
    creados = 0
    for paso, datos in PASOS.items():
        _, nuevo = EmailSecuencia.objects.get_or_create(
            email=email, paso=paso,
            defaults={
                "asunto": datos["asunto"],
                "cuerpo": datos["cuerpo"],
                "programado": ahora + timedelta(days=DIAS[paso]),
            })
        creados += int(nuevo)
    return creados


def _enlace_baja(email):
    from django.core import signing

    token = signing.dumps({"email": email}, salt="baja-correos")
    return f"https://{settings.SITE_DOMAIN}/baja-correos/{token}/"


def enviar_pendientes(limite=200):
    """Envía lo que ya venció. Devuelve (enviados, omitidos, fallidos)."""
    ahora = timezone.now()
    pendientes = EmailSecuencia.objects.filter(
        enviado=False, programado__lte=ahora).order_by("programado")[:limite]

    User = get_user_model()
    bajas = set(OptOut.objects.values_list("email", flat=True))

    enviados = omitidos = fallidos = 0
    for correo in pendientes:
        if correo.email in bajas or User.objects.filter(email__iexact=correo.email).exists():
            correo.enviado = True
            correo.enviado_en = ahora
            correo.error = "omitido: baja o ya registrado"
            correo.save(update_fields=["enviado", "enviado_en", "error"])
            omitidos += 1
            continue

        cuerpo = (
            f"{correo.cuerpo}\n\n"
            f"---\n"
            f"El informe completo, con plan de treinta días:\n"
            f"https://{settings.SITE_DOMAIN}/precios/\n\n"
            f"Para no recibir más correos: {_enlace_baja(correo.email)}\n"
            f"Para eliminar todos sus datos: https://{settings.SITE_DOMAIN}/baja/\n"
        )
        try:
            send_mail(correo.asunto, cuerpo, None, [correo.email], fail_silently=False)
            correo.enviado = True
            correo.enviado_en = ahora
            correo.save(update_fields=["enviado", "enviado_en"])
            enviados += 1
        except Exception as exc:
            correo.error = str(exc)[:300]
            correo.save(update_fields=["error"])
            fallidos += 1
            logger.exception("No se pudo enviar el paso %s a %s", correo.paso, correo.email)

    return enviados, omitidos, fallidos
