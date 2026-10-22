from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from . import questions as Q
from .models import Answer


def _bloque(slug):
    try:
        return next(b for b in Q.BLOCKS if b["slug"] == slug)
    except StopIteration:
        raise Http404("Bloque inexistente")


def _siguiente(slug):
    slugs = [b["slug"] for b in Q.BLOCKS]
    i = slugs.index(slug)
    return Q.BLOCKS[i + 1] if i + 1 < len(slugs) else None


@login_required
def start(request):
    incompletos = Q.bloques_incompletos(request.user)
    if incompletos:
        return redirect("intake:step", slug=incompletos[0]["slug"])
    return redirect("intake:revision")


@login_required
def step(request, slug):
    bloque = _bloque(slug)
    valores = Q.respuestas(request.user)

    if request.method == "POST":
        for q in bloque["questions"]:
            valor = (request.POST.get(q["key"]) or "").strip()
            if valor:
                Answer.objects.update_or_create(
                    user=request.user, key=q["key"], defaults={"value": valor})
            else:
                Answer.objects.filter(user=request.user, key=q["key"]).delete()
        siguientes = _siguiente(slug)
        if siguientes:
            messages.success(request, f"«{bloque['titulo']}» guardado.")
            return redirect("intake:step", slug=siguientes["slug"])
        messages.success(request, "Entrevista completa. Ya puede generar su informe.")
        return redirect("intake:revision")

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
    return render(request, "intake/revision.html", {
        "bloques": bloques,
        "contestadas": contestadas,
        "total": total,
        "pct": pct,
        "alertas": Q.alertas_riesgo(request.user),
        "minimo": Q.MINIMO_PARA_INFORME,
    })
