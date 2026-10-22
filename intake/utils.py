"""Utilidades del intake compartidas por las vistas."""
from .models import Answer


def entrevista_cambiada(user, informe):
    """True si el usuario editó alguna respuesta después de ese informe."""
    if informe is None:
        return True
    ultima = (Answer.objects.filter(user=user).order_by("-updated_at")
              .values_list("updated_at", flat=True).first())
    return bool(ultima and ultima > informe.created_at)
