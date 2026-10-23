"""Derecho de supresión: borrado real de los datos de una persona.

Cubre las cuatro bases donde puede haber datos personales: cuenta, diagnósticos públicos,
leads y legajos de la red. Es idempotente y no falla si el dato ya no existe.
"""
import logging

from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)


def borrar_por_email(email):
    """Elimina todo lo asociado a un correo. Devuelve el detalle de lo borrado."""
    from diagnostico.models import Diagnostico
    from red.models import Documento, Evento, Profesional
    from web.models import Lead

    email = (email or "").strip().lower()
    detalle = {"cuenta": 0, "diagnosticos": 0, "leads": 0, "profesionales": 0, "documentos": 0}
    if not email:
        return detalle

    with transaction.atomic():
        User = get_user_model()
        for usuario in User.objects.filter(email__iexact=email):
            usuario.delete()
            detalle["cuenta"] += 1

        detalle["diagnosticos"], _ = Diagnostico.objects.filter(email__iexact=email).delete()

        detalle["leads"], _ = Lead.objects.filter(email__iexact=email).delete()

        for p in Profesional.objects.filter(email__iexact=email):
            for doc in Documento.objects.filter(profesional=p):
                try:
                    doc.archivo.delete(save=False)
                except Exception:  # archivo ya inexistente
                    logger.warning("No se pudo borrar el archivo de %s", p.pk)
                doc.delete()
                detalle["documentos"] += 1
            Evento.objects.filter(profesional=p).delete()
            logger.info("Legajo de la red eliminado por derecho de supresión: %s", p.pk)
            # Se borra el legajo completo; queda registro en el log del sistema, sin datos
            # personales, para poder acreditar que la baja se ejecutó.
            p.delete()
            detalle["profesionales"] += 1

    return detalle
