"""Cliente mínimo de Mercado Pago (suscripciones/preapproval) sin dependencias externas."""
import json
import urllib.error
import urllib.request

from django.conf import settings


class MPError(Exception):
    def __init__(self, mensaje, estado=None, detalle=None):
        super().__init__(mensaje)
        self.estado = estado
        self.detalle = detalle or {}


def configurado():
    return bool(settings.MP_ACCESS_TOKEN)


def _llamar(metodo, ruta, cuerpo=None):
    if not configurado():
        raise MPError("Falta MP_ACCESS_TOKEN")
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(f"{settings.MP_API}{ruta}", data=datos, method=metodo)
    req.add_header("Authorization", f"Bearer {settings.MP_ACCESS_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Onto/1.0")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detalle = {}
        try:
            detalle = json.loads(exc.read().decode() or "{}")
        except Exception:
            pass
        raise MPError(detalle.get("message", "Error de Mercado Pago"), exc.code, detalle) from exc
    except urllib.error.URLError as exc:
        raise MPError(f"Sin conexión con Mercado Pago: {exc.reason}") from exc


def crear_preapproval(user, plan, precio, url_retorno):
    """Crea una suscripción mensual y devuelve (id, init_point)."""
    cuerpo = {
        "reason": f"Onto · plan {plan}",
        "external_reference": str(user.pk),
        "payer_email": user.email,
        "back_url": url_retorno,
        "status": "pending",
        "auto_recurring": {
            "frequency": 1,
            "frequency_type": "months",
            "transaction_amount": float(precio),
            "currency_id": "ARS",
        },
    }
    respuesta = _llamar("POST", "/preapproval", cuerpo)
    return respuesta.get("id"), respuesta.get("init_point") or respuesta.get("sandbox_init_point")


def obtener_preapproval(preapproval_id):
    return _llamar("GET", f"/preapproval/{preapproval_id}")


def cancelar_preapproval(preapproval_id):
    return _llamar("PUT", f"/preapproval/{preapproval_id}", {"status": "cancelled"})


def obtener_pago(payment_id):
    return _llamar("GET", f"/v1/payments/{payment_id}")
