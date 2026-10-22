import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import mp
from .models import Suscripcion
from .servicios import aplicar_preapproval, registrar_pago

logger = logging.getLogger(__name__)

PLANES_VALIDOS = ("pro", "estudio")


def _firma_valida(request, data_id):
    secreto = settings.MP_WEBHOOK_SECRET
    if not secreto:
        return False
    firma = request.headers.get("x-signature", "")
    partes = {}
    for trozo in firma.split(","):
        if "=" in trozo:
            clave, valor = trozo.split("=", 1)
            partes[clave.strip().lower()] = valor.strip()
    ts, v1 = partes.get("ts"), partes.get("v1")
    if not ts or not v1:
        return False
    request_id = request.headers.get("x-request-id", "")
    manifiesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    esperado = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)


@login_required
def suscribirse(request, plan):
    if plan not in PLANES_VALIDOS:
        return redirect("pricing")
    if not mp.configurado():
        messages.error(request, "Los pagos todavía no están habilitados.")
        return redirect("pricing")

    precio = settings.PLAN_PRICE_ARS[plan]
    retorno = request.build_absolute_uri(reverse("pagos:retorno"))
    try:
        preapproval_id, init_point = mp.crear_preapproval(request.user, plan, precio, retorno)
    except mp.MPError as exc:
        logger.warning("No se pudo crear la suscripción: %s", exc)
        if "same user" in str(exc).lower():
            messages.warning(
                request,
                "La cuenta que cobra no puede suscribirse a sí misma. Probá con un usuario de "
                "prueba de Mercado Pago o con otra cuenta.")
        else:
            messages.error(request, "Mercado Pago rechazó la operación. Intente en unos minutos.")
        return redirect("pricing")

    if not preapproval_id or not init_point:
        messages.error(request, "Mercado Pago no devolvió un enlace de pago.")
        return redirect("pricing")

    Suscripcion.objects.update_or_create(
        preapproval_id=preapproval_id,
        defaults={
            "user": request.user,
            "plan": plan,
            "monto": precio,
            "moneda": "ARS",
            "estado": "pending",
        })
    return redirect(init_point)


@login_required
def retorno(request):
    suscripcion = Suscripcion.objects.filter(user=request.user).first()
    return render(request, "pagos/retorno.html", {"suscripcion": suscripcion})


@login_required
def estado(request):
    suscripciones = Suscripcion.objects.filter(user=request.user)
    return render(request, "pagos/estado.html", {"suscripciones": suscripciones})


@login_required
@require_POST
def cancelar(request, pk):
    suscripcion = get_object_or_404(Suscripcion, pk=pk, user=request.user)
    if suscripcion.estado == "authorized":
        try:
            mp.cancelar_preapproval(suscripcion.preapproval_id)
        except mp.MPError as exc:
            logger.warning("No se pudo cancelar %s: %s", suscripcion.preapproval_id, exc)
            messages.error(request, "No pudimos cancelar en Mercado Pago. Escríbanos y lo resolvemos.")
            return redirect("pagos:estado")
    suscripcion.estado = "cancelled"
    suscripcion.save(update_fields=["estado"])
    messages.success(request, "Suscripción cancelada. Mantiene el acceso hasta la fecha ya pagada.")
    return redirect("pagos:estado")


@csrf_exempt
def webhook(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    data_id = request.GET.get("data.id") or request.GET.get("id") or ""
    tipo = request.GET.get("type") or request.GET.get("topic") or ""

    if not data_id:
        return JsonResponse({"detalle": "sin id"}, status=400)
    if not _firma_valida(request, data_id):
        logger.warning("Webhook con firma inválida para %s", data_id)
        return JsonResponse({"detalle": "firma inválida"}, status=401)

    try:
        if tipo in ("subscription_preapproval", "preapproval"):
            datos = mp.obtener_preapproval(data_id)
            aplicar_preapproval(datos)
        elif tipo == "payment":
            datos = mp.obtener_pago(data_id)
            registrar_pago(datos)
    except mp.MPError as exc:
        logger.warning("Webhook %s %s falló: %s", tipo, data_id, exc)
        return JsonResponse({"detalle": "reintentar"}, status=500)

    return HttpResponse("ok")
