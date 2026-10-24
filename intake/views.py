from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from reports.models import Report

from . import adaptativa
from . import questions as Q
from .models import Answer, Paso
from .utils import entrevista_cambiada


def _bloque(slug):
    try:
        return next(b for b in Q.BLOCKS if b["slug"] == slug)
    except StopIteration:
        raise Http404("Bloque inexistente")


def _siguiente(slug):
    slugs = [b["slug"] for b in Q.BLOCKS]
    i = slugs.index(slug)
    return Q.BLOCKS[i + 1] if i + 1 < len(slugs) else None


def _paso(entrevista, slug):
    paso, _ = Paso.objects.get_or_create(entrevista=entrevista, slug=slug)
    return paso


def _cerrar_paso(entrevista, slug, campos):
    paso = _paso(entrevista, slug)
    ahora = timezone.now()
    paso.guardado = ahora
    paso.campos = campos
    paso.segundos = max(int((ahora - paso.abierto).total_seconds()), 0)
    paso.save(update_fields=["guardado", "campos", "segundos"])


@login_required
def start(request):
    entrevista = adaptativa.entrevista_de(request.user)
    incompletos = Q.bloques_incompletos(request.user)
    if incompletos:
        return redirect("intake:step", slug=incompletos[0]["slug"])
    if entrevista and entrevista.variante.startswith("adaptativa") and not entrevista.saltada \
            and not entrevista.repreguntas:
        return redirect("intake:repreguntas")
    return redirect("intake:revision")


@login_required
def step(request, slug):
    bloque = _bloque(slug)
    valores = Q.respuestas(request.user)
    entrevista = adaptativa.entrevista_de(request.user)

    if request.method == "POST":
        contestadas = 0
        for q in bloque["questions"]:
            valor = (request.POST.get(q["key"]) or "").strip()
            if valor:
                contestadas += 1
                Answer.objects.update_or_create(
                    user=request.user, key=q["key"], defaults={"value": valor})
            else:
                Answer.objects.filter(user=request.user, key=q["key"]).delete()
        if entrevista:
            _cerrar_paso(entrevista, slug, contestadas)
        siguientes = _siguiente(slug)
        if siguientes:
            messages.success(request, f"«{bloque['titulo']}» guardado.")
            return redirect("intake:step", slug=siguientes["slug"])
        messages.success(request, "Entrevista completa.")
        if entrevista:
            entrevista.completada = timezone.now()
            entrevista.save(update_fields=["completada"])
            if entrevista.variante.startswith("adaptativa") and not entrevista.saltada:
                return redirect("intake:repreguntas")
        return redirect("intake:revision")

    if entrevista:
        _paso(entrevista, slug)
    contestadas, total, pct = Q.progress(request.user)
    return render(request, "intake/step.html", {
        "bloque": bloque,
        "items": [(q, valores.get(q["key"], "")) for q in bloque["questions"]],
        "respuestas": valores,
        "pct": pct,
        "contestadas": contestadas,
        "total": total,
        "numero": [b["slug"] for b in Q.BLOCKS].index(slug) + 1,
        "total_bloques": len(Q.BLOCKS),
    })


@login_required
def repreguntas(request):
    """Ronda adaptativa: hasta cinco preguntas armadas sobre lo que ya escribió."""
    entrevista = adaptativa.entrevista_de(request.user)
    if entrevista is None:
        return redirect("intake:start")

    if request.method == "POST":
        if request.POST.get("accion") == "saltar":
            entrevista.saltada = True
            entrevista.save(update_fields=["saltada"])
            messages.info(request, "Sin problema: puede generar su informe cuando quiera.")
            return redirect("intake:revision")
        contestadas = adaptativa.guardar_respuestas(entrevista, request.POST)
        if contestadas:
            messages.success(request, f"Guardamos {contestadas} respuesta(s).")
        else:
            messages.info(request, "No escribió ninguna respuesta: el informe se hará con la primera ronda.")
        return redirect("intake:revision")

    if entrevista.variante != "adaptativa-v1":
        return redirect("intake:revision")

    if not entrevista.repreguntas:
        entrevista, error = adaptativa.generar(request.user)
        if not entrevista.repreguntas:
            messages.info(request, "La ronda de repreguntas no está disponible ahora. "
                                   "Puede generar su informe igual.")
            return redirect("intake:revision")

    return render(request, "intake/repreguntas.html", {
        "entrevista": entrevista,
        "items": entrevista.repreguntas,
    })


@login_required
def revision(request):
    r = Q.respuestas(request.user)
    bloques = []
    for b in Q.BLOCKS:
        bloques.append({
            "slug": b["slug"],
            "titulo": b["titulo"],
            "items": [(q["label"], r.get(q["key"], "")) for q in b["questions"]],
            "respondidas": sum(1 for q in b["questions"] if r.get(q["key"])),
            "total": len(b["questions"]),
        })
    contestadas, total, pct = Q.progress(request.user)
    informe = Report.objects.filter(user=request.user).order_by("-numero").first()
    entrevista = adaptativa.entrevista_de(request.user, crear=False)
    return render(request, "intake/revision.html", {
        "bloques": bloques,
        "contestadas": contestadas,
        "total": total,
        "pct": pct,
        "alertas": Q.alertas_riesgo(request.user),
        "minimo": Q.MINIMO_PARA_INFORME,
        "informe": informe,
        "rehacer": entrevista_cambiada(request.user, informe),
        "entrevista": entrevista,
        "repreguntas": (entrevista.repreguntas if entrevista else []),
    })
