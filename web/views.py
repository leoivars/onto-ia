import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from intake import questions as Q
from reports.models import Report

from .forms import LeadForm, SignupForm
from .models import InviteCode, Lead, perfil_de


def landing(request):
    if request.user.is_authenticated:
        return redirect("panel")
    return render(request, "web/landing.html", {"bloques": Q.BLOCKS})


def pricing(request):
    form = LeadForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        Lead.objects.get_or_create(
            email=form.cleaned_data["email"].strip().lower(), defaults={"origen": "precios"})
        messages.success(request, "Listo. Le escribimos cuando abramos los cupos.")
        return redirect("pricing")
    return render(request, "web/pricing.html", {"lead_form": form})


def legal(request):
    return render(request, "web/legal.html", {"contacto": settings.CONTACT_EMAIL})


def signup(request):
    if request.user.is_authenticated:
        return redirect("panel")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        perfil = perfil_de(user)
        perfil.nombre = form.cleaned_data["nombre"].strip()
        perfil.consent_at = timezone.now()
        perfil.save()
        login(request, user)
        messages.success(request, "Cuenta creada. Empecemos por conocerlo.")
        return redirect("intake:start")
    return render(request, "web/signup.html", {"form": form})


@login_required
def dashboard(request):
    perfil = perfil_de(request.user)
    respondidas, total, pct = Q.progress(request.user)
    informe = Report.objects.filter(user=request.user).order_by("-numero").first()
    return render(request, "web/dashboard.html", {
        "perfil": perfil,
        "respondidas": respondidas,
        "total": total,
        "pct": pct,
        "informe": informe,
        "sin_responder": Q.bloques_incompletos(request.user),
        "stats": Q.estadisticas(request.user),
        "puede_generar": perfil.puede_generar and respondidas >= Q.MINIMO_PARA_INFORME,
        "minimo": Q.MINIMO_PARA_INFORME,
        "bloques": Q.BLOCKS,
        "total_bloques": len(Q.BLOCKS),
    })


@login_required
def account(request):
    return render(request, "web/account.html", {"perfil": perfil_de(request.user)})


@login_required
def export_data(request):
    """Derecho de acceso (Ley 25.326): descarga íntegra de los datos del consultante."""
    perfil = perfil_de(request.user)
    datos = {
        "cuenta": {
            "email": request.user.email,
            "nombre": perfil.nombre,
            "alta": perfil.created_at.isoformat(),
            "plan": perfil.plan_efectivo,
            "consentimiento": perfil.consent_at.isoformat() if perfil.consent_at else None,
        },
        "respuestas": [
            {"clave": a.key, "pregunta": Q.FLAT.get(a.key, {}).get("label", a.key),
             "respuesta": a.value, "actualizado": a.updated_at.isoformat()}
            for a in request.user.answers.order_by("key")
        ],
        "informes": [
            {
                "numero": r.numero, "titulo": r.titulo, "fecha": r.created_at.isoformat(),
                "motor": r.engine, "secciones": r.secciones,
            }
            for r in request.user.reports.order_by("numero")
        ],
    }
    response = HttpResponse(
        json.dumps(datos, ensure_ascii=False, indent=2), content_type="application/json")
    response["Content-Disposition"] = 'attachment; filename="mis-datos-observador.json"'
    return response


@login_required
@require_POST
def delete_account(request):
    user = request.user
    user.delete()
    messages.success(request, "Su cuenta y todos sus datos fueron eliminados.")
    return redirect("landing")


@login_required
@require_POST
def redeem_code(request):
    codigo = (request.POST.get("code") or "").strip().upper()
    if not codigo:
        messages.error(request, "Ingrese un código.")
        return redirect("account")
    try:
        inv = InviteCode.objects.get(code=codigo)
    except InviteCode.DoesNotExist:
        messages.error(request, "El código no es válido.")
        return redirect("account")
    if inv.used_by_id and inv.used_by_id != request.user.id:
        messages.error(request, "Ese código ya fue utilizado.")
        return redirect("account")

    perfil = perfil_de(request.user)
    base = max(perfil.pro_until or timezone.localdate(), timezone.localdate())
    perfil.plan = inv.plan
    perfil.pro_until = base + timedelta(days=inv.dias)
    perfil.save(update_fields=["plan", "pro_until"])
    inv.used_by = request.user
    inv.used_at = timezone.now()
    inv.save(update_fields=["used_by", "used_at"])
    messages.success(request, f"Acceso {inv.get_plan_display()} activo por {inv.dias} días.")
    return redirect("panel")
