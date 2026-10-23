"""Agregados diarios: se agrupa antes de borrar, para no perder la serie histórica."""
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone


def agregar_dia(fecha):
    """Recalcula el resumen de un día. Idempotente: se puede correr varias veces."""
    from .models import ResumenDiario, Visita

    filas = (Visita.objects.filter(creada__date=fecha)
             .values("origen", "ruta")
             .annotate(vistas=Count("id"), sesiones=Count("sesion", distinct=True)))

    ResumenDiario.objects.filter(fecha=fecha).delete()
    creados = 0
    for fila in filas:
        ResumenDiario.objects.create(
            fecha=fecha,
            origen=(fila["origen"] or "directo")[:60],
            ruta=(fila["ruta"] or "/")[:120],
            vistas=fila["vistas"],
            sesiones=fila["sesiones"],
        )
        creados += 1
    return creados


def agregar_rango(desde, hasta):
    """Agrega día por día el rango indicado (ambos inclusive)."""
    total = 0
    dia = desde
    while dia <= hasta:
        total += agregar_dia(dia)
        dia += timedelta(days=1)
    return total


def agregar_pendientes(dias=3):
    """Recalcula los últimos días cerrados: cubre el caso de un cron que corre a la mañana."""
    hoy = timezone.localdate()
    return agregar_rango(hoy - timedelta(days=dias), hoy)
