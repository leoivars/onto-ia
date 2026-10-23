import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from intake import questions as Q
from reports.models import Report

from .forms import LeadForm, SignupForm
from .metricas import resumen as resumen_metricas
from .metricas import historico, trafico
from .models import InviteCode, Lead, perfil_de
from .visitas import origen_de


def landing(request):
    if request.user.is_authenticated:
        return redirect("panel")
    return render(request, "web/landing.html", {"bloques": Q.BLOCKS})


def ayuda_view(request):
    from .ayuda import LINEAS, texto_derivacion

    return render(request, "web/ayuda.html", {
        "lineas": LINEAS, "derivacion": texto_derivacion()})


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
        perfil.origen = origen_de(request)
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
    from . import seguridad

    return render(request, "web/account.html", {
        "perfil": perfil_de(request.user),
        "totp": seguridad.dispositivo(request.user),
    })


@staff_member_required
def metricas(request):
    datos = resumen_metricas()
    datos["trafico"] = trafico()
    datos["historico"] = historico()
    from . import analitica_ig

    datos["ig"] = analitica_ig.resumen()
    return render(request, "web/metricas.html", {"m": datos})


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
    from .olvido import borrar_por_email

    detalle = borrar_por_email(request.user.email)
    messages.success(
        request,
        f"Su cuenta y sus datos fueron eliminados ({detalle['cuenta']} cuenta, "
        f"{detalle['diagnosticos']} diagnósticos).")
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


# --------------------------------------------------------------- derecho de supresión

@require_http_methods(["GET", "POST"])
def baja(request):
    """Pedido de supresión: se confirma por correo para que nadie borre datos ajenos."""
    error = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        try:
            validate_email(email)
        except ValidationError:
            error = "Revise el correo."
        if not error:
            token = signing.dumps({"email": email}, salt="baja")
            enlace = f"https://{settings.SITE_DOMAIN}/baja/{token}/"
            send_mail(
                "Confirmar borrado de datos · Onto",
                (
                    "Recibimos un pedido para eliminar los datos asociados a este correo.\n\n"
                    f"Para confirmarlo, abra este enlace (vale 48 horas):\n{enlace}\n\n"
                    "Si usted no lo pidió, ignore este mensaje: no se borra nada.\n\n"
                    "—\nOnto · Privacidad"
                ),
                None, [email], fail_silently=True)
            return render(request, "web/baja_enviada.html", {"email": email})
    return render(request, "web/baja.html", {"error": error})


@require_http_methods(["GET"])
def baja_confirmar(request, token):
    from .olvido import borrar_por_email

    try:
        datos = signing.loads(token, salt="baja", max_age=48 * 3600)
    except signing.SignatureExpired:
        return render(request, "web/baja_error.html",
                      {"motivo": "El enlace venció. Pida uno nuevo."}, status=410)
    except signing.BadSignature:
        return render(request, "web/baja_error.html",
                      {"motivo": "El enlace no es válido."}, status=410)

    detalle = borrar_por_email(datos.get("email"))
    return render(request, "web/baja_confirmada.html",
                  {"email": datos.get("email"), "detalle": detalle})


@require_http_methods(["GET"])
def baja_correos(request, token):
    """Baja de la secuencia de correos. No borra datos: para eso está /baja/."""
    from .models import EmailSecuencia, OptOut

    try:
        datos = signing.loads(token, salt="baja-correos")
    except signing.BadSignature:
        return render(request, "web/baja_error.html",
                      {"motivo": "El enlace no es válido."}, status=410)

    email = (datos.get("email") or "").strip().lower()
    OptOut.objects.get_or_create(email=email)
    EmailSecuencia.objects.filter(email=email, enviado=False).update(
        enviado=True, error="baja del correo")
    return render(request, "web/baja_correos.html", {"email": email})


@require_http_methods(["GET"])
def publicacion_imagen(request, nombre):
    """Expone las imágenes que se publican en redes: solo nombres válidos de esa carpeta."""
    import re
    from pathlib import Path

    from django.http import FileResponse, Http404

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,60}$", nombre):
        raise Http404
    ruta = Path(settings.MEDIA_ROOT) / "publicaciones" / f"{nombre}.jpg"
    if not ruta.exists():
        raise Http404
    respuesta = FileResponse(open(ruta, "rb"), content_type="image/jpeg")
    respuesta["Cache-Control"] = "public, max-age=31536000, immutable"
    return respuesta


# --------------------------------------------------------------- segundo factor

@login_required
def configurar_2fa(request):
    from django.contrib.auth.hashers import make_password

    from . import seguridad
    from .models import DispositivoTOTP

    if seguridad.es_administrador(request.user):
        destino = "admin:index"
    else:
        destino = "account"

    dispositivo = seguridad.dispositivo(request.user)
    if dispositivo and dispositivo.confirmado_en:
        request.session["otp_ok"] = True
        return redirect(request.GET.get("next") or destino)

    if not dispositivo:
        dispositivo = DispositivoTOTP.objects.create(
            user=request.user, secreto=seguridad.nuevo_secreto())

    error = ""
    if request.method == "POST":
        if seguridad.codigo_valido(dispositivo.secreto, request.POST.get("codigo")):
            claros, hashes = seguridad.generar_respaldo()
            dispositivo.confirmado_en = timezone.now()
            dispositivo.codigos_respaldo = hashes
            dispositivo.save(update_fields=["confirmado_en", "codigos_respaldo"])
            request.session["otp_ok"] = True
            return render(request, "web/2fa_respaldo.html", {"codigos": claros})
        error = "El código no coincide. Revise la hora del teléfono y pruebe otra vez."

    uri = seguridad.uri_otpauth(request.user, dispositivo.secreto)
    return render(request, "web/2fa_configurar.html", {
        "qr": seguridad.qr_data_uri(uri), "secreto": dispositivo.secreto, "error": error,
        "next": request.GET.get("next", ""),
    })


@login_required
def verificar_2fa(request):
    from . import seguridad

    dispositivo = seguridad.dispositivo(request.user)
    if not dispositivo or not dispositivo.confirmado_en:
        return redirect("2fa_configurar")

    error = ""
    if request.method == "POST":
        codigo = request.POST.get("codigo")
        if seguridad.codigo_valido(dispositivo.secreto, codigo) or \
                seguridad.consumir_respaldo(dispositivo, codigo):
            request.session["otp_ok"] = True
            if not seguridad.codigo_valido(dispositivo.secreto, codigo):
                dispositivo.ultimo_uso = timezone.now()
                dispositivo.save(update_fields=["ultimo_uso"])
            siguiente = request.POST.get("next") or ""
            if siguiente.startswith("/"):
                return redirect(siguiente)
            if request.user.is_staff:
                return redirect("admin:index")
            return redirect("panel")
        error = "Código incorrecto o vencido."

    return render(request, "web/2fa_verificar.html", {"error": error,
                                                      "next": request.GET.get("next", "")})


@login_required
@require_POST
def desactivar_2fa(request):
    from . import seguridad

    if seguridad.es_administrador(request.user):
        messages.error(request, "El segundo factor es obligatorio en cuentas de administración.")
        return redirect("account")

    dispositivo = seguridad.dispositivo(request.user)
    if dispositivo:
        dispositivo.delete()
    request.session.pop("otp_ok", None)
    messages.success(request, "Segundo factor desactivado. Puede volver a activarlo cuando quiera.")
    return redirect("account")
