"""Métricas de validación: ¿el producto sirve antes de cobrarlo?"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count

from intake import questions as Q

from .models import Profile
from .models import Lead


def resumen():
    User = get_user_model()
    from reports.models import Feedback, Report

    usuarios = User.objects.filter(is_staff=False)
    total = usuarios.count()
    completas = 0
    for user in usuarios:
        respondidas, _, _ = Q.progress(user)
        if respondidas >= Q.MINIMO_PARA_INFORME:
            completas += 1

    informes = Report.objects.all()
    con_informe = informes.values("user").distinct().count()
    con_dos = (informes.values("user").annotate(n=Count("id")).filter(n__gte=2).count())
    por_motor = dict(informes.values_list("engine").annotate(n=Count("id")))

    feedback = Feedback.objects.all()
    resonancia = feedback.aggregate(p=Avg("resonancia"))["p"]
    con_profundizar = feedback.exclude(profundizar="").count()

    # Días entre el primer y el segundo informe
    demoras = []
    for fila in informes.values("user").annotate(n=Count("id")).filter(n__gte=2):
        fechas = list(
            informes.filter(user_id=fila["user"]).order_by("created_at")
            .values_list("created_at", flat=True)[:2])
        if len(fechas) == 2:
            demoras.append((fechas[1] - fechas[0]).days)
    demora_promedio = round(sum(demoras) / len(demoras), 1) if demoras else None

    planes = dict(Profile.objects.values_list("plan").annotate(n=Count("id")))

    return {
        "usuarios": total,
        "entrevistas_completas": completas,
        "pct_entrevista": round(100 * completas / total) if total else 0,
        "informes": informes.count(),
        "usuarios_con_informe": con_informe,
        "usuarios_con_dos_informes": con_dos,
        "pct_profundiza": round(100 * con_dos / con_informe) if con_informe else 0,
        "por_motor": por_motor,
        "feedback": feedback.count(),
        "resonancia": round(resonancia, 2) if resonancia else None,
        "pct_pide_profundizar": round(100 * con_profundizar / feedback.count()) if feedback.count() else 0,
        "demora_promedio": demora_promedio,
        "planes": planes,
        "leads": Lead.objects.count(),
        "hoy": date.today(),
    }
