"""Segundo factor obligatorio para administradores, con Google Authenticator.

Solo entra al panel y a las métricas quien presentó el código de seis dígitos. El secreto vive
en la base, y cada código de respaldo se guarda con hash y se consume una sola vez.
"""
import base64
import io
import secrets

import pyotp
import qrcode
from django.contrib.auth.hashers import check_password, make_password
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

RUTAS_LIBRES = ("/seguridad/", "/salir/", "/ingresar/", "/static/", "/media/", "/favicon",
                "/admin/logout/", "/admin/login/", "/baja/", "/ayuda/")
CODIGOS_RESPALDO = 8


def es_administrador(user):
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))


def requiere_verificacion(user):
    """Para administradores es obligatorio; un cliente solo si lo activó."""
    if not user or not user.is_authenticated:
        return False
    if es_administrador(user):
        return True
    existente = dispositivo(user)
    return bool(existente and existente.confirmado_en)


def dispositivo(user):
    from .models import DispositivoTOTP

    return DispositivoTOTP.objects.filter(user=user).first()


def nuevo_secreto():
    return pyotp.random_base32()


def uri_otpauth(user, secreto, emisor="Onto"):
    return pyotp.totp.TOTP(secreto).provisioning_uri(name=user.email or user.username,
                                                      issuer_name=emisor)


def qr_data_uri(texto):
    imagen = qrcode.make(texto, box_size=8, border=2)
    buffer = io.BytesIO()
    imagen.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def codigo_valido(secreto, codigo):
    return pyotp.TOTP(secreto).verify((codigo or "").strip().replace(" ", ""), valid_window=1)


def generar_respaldo():
    """Devuelve (codigos_en_claro, codigos_con_hash). Los claros se muestran una sola vez."""
    claros = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(CODIGOS_RESPALDO)]
    return claros, [make_password(c) for c in claros]


def consumir_respaldo(dispositivo_obj, codigo):
    codigo = (codigo or "").strip().lower()
    if not codigo:
        return False
    for indice, guardado in enumerate(dispositivo_obj.codigos_respaldo):
        if check_password(codigo, guardado):
            restantes = list(dispositivo_obj.codigos_respaldo)
            restantes.pop(indice)
            dispositivo_obj.codigos_respaldo = restantes
            dispositivo_obj.ultimo_uso = timezone.now()
            dispositivo_obj.save(update_fields=["codigos_respaldo", "ultimo_uso"])
            return True
    return False


class SegundoFactorMiddleware:
    """Corta el paso a los administradores que no completaron el segundo factor."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if requiere_verificacion(request.user) and not request.session.get("otp_ok"):
            if not any(request.path.startswith(r) for r in RUTAS_LIBRES):
                tiene = dispositivo(request.user)
                destino = ("2fa_verificar" if tiene and tiene.confirmado_en
                           else "2fa_configurar")
                return redirect(f"{reverse(destino)}?next={request.path}")
        return self.get_response(request)
