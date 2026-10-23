import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from intake import questions as Q
from intake.utils import entrevista_cambiada
from web.models import perfil_de

from . import engine
from . import cola as cola_mod
from . import ai
from .models import Feedback, InformeEnCola, Report

logger = logging.getLogger(__name__)


@login_required
def lista(request):
    informes = Report.objects.filter(user=request.user).prefetch_related("feedbacks")
    return render(request, "reports/list.html", {"informes": informes})


def _entrevista_cambiada(user, informe):  # compatibilidad
    return entrevista_cambiada(user, informe)


@login_required
@require_POST
def generar(request):
    respondidas, _, _ = Q.progress(request.user)
    if respondidas < Q.MINIMO_PARA_INFORME:
        messages.error(
            request,
            f"Necesitamos al menos {Q.MINIMO_PARA_INFORME} respuestas para escribir un informe "
            f"que valga la pena. Lleva {respondidas}.")
        return redirect("intake:revision")

    perfil = perfil_de(request.user)
    if not perfil.puede_generar:
        messages.warning(
            request,
            "Alcanzó su límite de informes de este mes. Puede mejorar el plan o esperar el "
            "próximo ciclo.")
        return redirect("pricing")

    ultimo = Report.objects.filter(user=request.user).first()
    if ultimo and not request.POST.get("forzar"):
        if not ultimo.feedbacks.exists() and not _entrevista_cambiada(request.user, ultimo):
            messages.info(
                request,
                "Su informe ya está generado. Si quiere uno nuevo, deje una devolución sobre "
                "éste o modifique la entrevista; así el segundo aporta algo distinto.")
            return redirect("reports:detalle", pk=ultimo.pk)

    cola_previa = InformeEnCola.objects.filter(user=request.user, estado="pendiente").first()
    if cola_previa:
        messages.info(
            request,
            "Su informe ya está en cola. Estamos con un problema técnico en el motor de "
            "escritura y lo estamos resolviendo; apenas se restablezca lo generamos y le "
            "avisamos por correo. No hace falta pedirlo de nuevo.")
        return redirect("panel")

    try:
        informe = engine.generar(request.user)
    except ai.SinCreditos as exc:
        cola, _ = cola_mod.encolar(request.user, str(exc))
        messages.warning(
            request,
            "Su informe quedó en cola. En este momento el motor de escritura no está disponible "
            "y estamos trabajando para solucionarlo a la brevedad. Le avisamos por correo en "
            "cuanto esté listo: no hace falta que vuelva a pedirlo.")
        return redirect("panel")
    except Exception:
        logger.exception("Falló la generación de informe para %s", request.user.pk)
        messages.error(request, "No pudimos escribir el informe. Intente de nuevo en unos minutos.")
        return redirect("panel")

    if informe.es_ia:
        messages.success(request, "Informe generado. Léalo con lápiz en mano y devuélvanos feedback.")
    else:
        messages.info(
            request,
            "Informe generado con el motor local de demostración: la estructura y el análisis son "
            "reales, pero la redacción no usa IA. Configure AI_API_KEY para activar el motor completo.")
    return redirect("reports:detalle", pk=informe.pk)


@login_required
def detalle(request, pk):
    informe = get_object_or_404(Report, pk=pk, user=request.user)
    perfil = perfil_de(request.user)
    return render(request, "reports/detail.html", {
        "informe": informe,
        "feedbacks": informe.feedbacks.all(),
        "puede_generar": perfil.puede_generar,
        "disponibles": perfil.informes_disponibles,
        "cuota": perfil.cuota_mensual,
    })


@login_required
@require_POST
def feedback(request, pk):
    informe = get_object_or_404(Report, pk=pk, user=request.user)
    try:
        resonancia = int(request.POST.get("resonancia") or 3)
    except ValueError:
        resonancia = 3
    resonancia = min(5, max(1, resonancia))

    Feedback.objects.create(
        report=informe,
        resonancia=resonancia,
        aciertos=(request.POST.get("aciertos") or "").strip(),
        desaciertos=(request.POST.get("desaciertos") or "").strip(),
        profundizar=(request.POST.get("profundizar") or "").strip(),
    )
    messages.success(request, "Gracias. Su devolución entra en el próximo informe.")
    return redirect("reports:detalle", pk=informe.pk)


@login_required
def imprimir(request, pk):
    informe = get_object_or_404(Report, pk=pk, user=request.user)
    return render(request, "reports/print.html", {"informe": informe})
