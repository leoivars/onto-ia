from datetime import date, timedelta

from django.conf import settings

from web.models import perfil_de

from .models import Pago, Suscripcion


def aplicar_preapproval(datos):
    """Sincroniza una suscripción con el estado que devuelve Mercado Pago."""
    preapproval_id = datos.get("id")
    if not preapproval_id:
        return None
    suscripcion = Suscripcion.objects.filter(preapproval_id=preapproval_id).first()
    if not suscripcion:
        return None

    estado_anterior = suscripcion.estado
    estado = (datos.get("status") or "").lower()
    if estado:
        suscripcion.estado = estado if estado in dict(Suscripcion.ESTADOS) else "pending"

    auto = datos.get("auto_recurring") or {}
    if auto.get("transaction_amount") is not None:
        suscripcion.monto = auto["transaction_amount"]
    if auto.get("currency_id"):
        suscripcion.moneda = auto["currency_id"]

    proximo = datos.get("next_payment_date")
    if proximo:
        try:
            suscripcion.proximo_pago = date.fromisoformat(proximo[:10])
        except ValueError:
            pass

    suscripcion.save()

    # Solo se extiende el acceso en la transición a autorizada (idempotencia).
    if suscripcion.estado == "authorized" and estado_anterior != "authorized":
        perfil = perfil_de(suscripcion.user)
        hoy = date.today()
        base = perfil.pro_until if perfil.pro_until and perfil.pro_until > hoy else hoy
        perfil.plan = suscripcion.plan if suscripcion.plan in settings.PLAN_QUOTA else "pro"
        perfil.pro_until = base + timedelta(days=31)
        perfil.save(update_fields=["plan", "pro_until"])

    return suscripcion


def registrar_pago(datos):
    payment_id = datos.get("id")
    if not payment_id:
        return None
    referencia = str(datos.get("external_reference") or "")
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=referencia).first() if referencia.isdigit() else None
    if not user:
        user = _usuario_de_suscripcion(datos)
    if not user:
        return None

    pago, _ = Pago.objects.update_or_create(
        mp_payment_id=str(payment_id),
        defaults={
            "user": user,
            "monto": datos.get("transaction_amount") or 0,
            "moneda": datos.get("currency_id") or "ARS",
            "estado": (datos.get("status") or "")[:30],
            "crudo": datos,
        },
    )
    return pago


def _usuario_de_suscripcion(datos):
    preapproval = (datos.get("metadata") or {}).get("preapproval_id") or datos.get("preapproval_id")
    if not preapproval:
        return None
    suscripcion = Suscripcion.objects.filter(preapproval_id=preapproval).first()
    return suscripcion.user if suscripcion else None
