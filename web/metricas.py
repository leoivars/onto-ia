"""Métricas de validación: ¿el producto sirve antes de cobrarlo?"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.conf import settings

from reports import engine as motor_ia

from intake import questions as P

from .models import Profile
from .models import Lead


def resumen():
    User = get_user_model()
    from reports.models import Feedback, Report
    from diagnostico.models import Diagnostico

    usuarios = User.objects.filter(is_staff=False)
    total = usuarios.count()
    completas = 0
    for user in usuarios:
        respondidas, _, _ = P.progress(user)
        if respondidas >= P.MINIMO_PARA_INFORME:
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

    consumo = informes.aggregate(
        entrada=Sum("tokens_in"), salida=Sum("tokens_out"),
        cache=Sum("tokens_cache"), costo=Sum("costo_usd"))
    con_ia = informes.filter(engine="ia").count()
    entrada = consumo["entrada"] or 0
    cache = consumo["cache"] or 0

    hoy = date.today()
    con_ia_qs = informes.filter(engine="ia")
    por_usuario = list(con_ia_qs.values("user__email").annotate(
        costo=Sum("costo_usd"), informes=Count("id"),
        costo_hoy=Sum("costo_usd", filter=Q(created_at__date=hoy)),
        ultimo=Max("created_at")).order_by("-costo")[:10])
    por_dia = list(con_ia_qs.annotate(dia=TruncDate("created_at")).values("dia").annotate(
        costo=Sum("costo_usd"), informes=Count("id")).order_by("-dia")[:7])
    costo_hoy = con_ia_qs.filter(created_at__date=hoy).aggregate(c=Sum("costo_usd"))["c"] or 0

    from diagnostico.models import Diagnostico

    diagnosticos = Diagnostico.objects.count()
    conversiones = sum(1 for d in Diagnostico.objects.only("email") if d.conversion)

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
        "tokens_entrada": entrada,
        "tokens_salida": consumo["salida"] or 0,
        "tokens_cache": cache,
        "pct_cache": round(100 * cache / entrada) if entrada else 0,
        "costo_total": float(consumo["costo"] or 0),
        "costo_promedio": round(float(consumo["costo"] or 0) / con_ia, 5) if con_ia else 0,
        "con_ia": con_ia,
        "costo_hoy": float(costo_hoy),
        "por_usuario": por_usuario,
        "por_dia": por_dia,
        "gasto_mes": round(motor_ia.gasto_mes(), 5),
        "presupuesto": settings.AI_PRESUPUESTO_USD,
        "pct_presupuesto": round(100 * motor_ia.gasto_mes() / settings.AI_PRESUPUESTO_USD)
        if settings.AI_PRESUPUESTO_USD else 0,
        "limite_usuario": settings.AI_LIMITE_USUARIO_USD,
        "diagnosticos": diagnosticos,
        "conversiones_diag": conversiones,
        "pct_conversion_diag": round(100 * conversiones / diagnosticos) if diagnosticos else 0,
        "hoy": hoy,
    }


def trafico(dias=30):
    """Embudo de adquisición: visitas, origen, diagnósticos y registros."""
    from datetime import timedelta

    from django.utils import timezone as tz

    from .models import Visita

    desde = tz.now() - timedelta(days=dias)
    visitas = Visita.objects.filter(creada__gte=desde)
    vistas = visitas.count()
    sesiones = visitas.values("sesion").distinct().count()

    por_origen = list(
        visitas.values("origen").annotate(vistas=Count("id"), sesiones=Count("sesion", distinct=True))
        .order_by("-vistas")[:12])
    for fila in por_origen:
        fila["origen"] = fila["origen"] or "directo"

    diag = list(Diagnostico.objects.filter(created_at__gte=desde)
                .values("origen").annotate(n=Count("id")).order_by("-n"))
    for fila in diag:
        fila["origen"] = fila["origen"] or "sin dato"

    registros = list(Profile.objects.filter(created_at__gte=desde)
                     .values("origen").annotate(n=Count("id")).order_by("-n"))
    for fila in registros:
        fila["origen"] = fila["origen"] or "sin dato"

    total_diag = sum(f["n"] for f in diag)
    total_reg = sum(f["n"] for f in registros)

    return {
        "dias": dias,
        "vistas": vistas,
        "sesiones": sesiones,
        "por_origen": por_origen,
        "diagnosticos": total_diag,
        "diagnosticos_origen": diag,
        "registros": total_reg,
        "registros_origen": registros,
        "pct_diag": round(100 * total_diag / sesiones) if sesiones else 0,
        "pct_reg": round(100 * total_reg / total_diag) if total_diag else 0,
    }


def historico(meses=12):
    """Serie mensual a partir de los agregados: sirve para comparar temporadas."""
    from datetime import timedelta

    from django.db.models.functions import TruncMonth
    from django.utils import timezone as tz

    from diagnostico.models import Diagnostico

    from .models import ResumenDiario

    hoy = tz.localdate()
    inicio = hoy.replace(day=1)
    for _ in range(meses - 1):
        inicio = (inicio - timedelta(days=1)).replace(day=1)

    visitas = {
        (f["mes"].year, f["mes"].month): {"vistas": f["vistas"], "sesiones": f["sesiones"]}
        for f in ResumenDiario.objects.filter(fecha__gte=inicio)
        .annotate(mes=TruncMonth("fecha"))
        .values("mes").annotate(vistas=Sum("vistas"), sesiones=Sum("sesiones"))
    }
    diags = {
        (f["mes"].year, f["mes"].month): f["n"]
        for f in Diagnostico.objects.filter(created_at__date__gte=inicio)
        .annotate(mes=TruncMonth("created_at")).values("mes").annotate(n=Count("id"))
    }
    regs = {
        (f["mes"].year, f["mes"].month): f["n"]
        for f in Profile.objects.filter(created_at__date__gte=inicio)
        .annotate(mes=TruncMonth("created_at")).values("mes").annotate(n=Count("id"))
    }

    serie, cursor = [], inicio
    for _ in range(meses):
        clave = (cursor.year, cursor.month)
        serie.append({
            "etiqueta": cursor.strftime("%m/%Y"),
            "vistas": visitas.get(clave, {}).get("vistas", 0),
            "sesiones": visitas.get(clave, {}).get("sesiones", 0),
            "diagnosticos": diags.get(clave, 0),
            "registros": regs.get(clave, 0),
        })
        cursor = (cursor + timedelta(days=32)).replace(day=1)

    return serie
