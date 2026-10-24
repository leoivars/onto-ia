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
from django.urls import reverse
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
    from .metricas import embudo_entrevista

    datos["entrevista"] = embudo_entrevista()
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
    from email.utils import formatdate
    from pathlib import Path

    from django.http import FileResponse, Http404

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,60}$", nombre):
        raise Http404
    ruta = Path(settings.MEDIA_ROOT) / "publicaciones" / f"{nombre}.jpg"
    if not ruta.exists():
        raise Http404
    respuesta = FileResponse(open(ruta, "rb"), content_type="image/jpeg")
    # Cinco minutos, no un año: estas piezas se regeneran y la caché del borde las retenía.
    respuesta["Cache-Control"] = "public, max-age=300"
    respuesta["Last-Modified"] = formatdate(ruta.stat().st_mtime, usegmt=True)
    return respuesta


def publicacion_video(request, nombre):
    """Expone los reels en /ig/<nombre>.mp4: Instagram los descarga desde acá."""
    import re
    from email.utils import formatdate
    from pathlib import Path

    from django.http import FileResponse, Http404

    if not re.match(r"^[a-z0-9][a-z0-9-]{1,60}$", nombre):
        raise Http404
    ruta = Path(settings.MEDIA_ROOT) / "publicaciones" / f"{nombre}.mp4"
    if not ruta.exists():
        raise Http404
    respuesta = FileResponse(open(ruta, "rb"), content_type="video/mp4")
    respuesta["Cache-Control"] = "public, max-age=300"
    respuesta["Last-Modified"] = formatdate(ruta.stat().st_mtime, usegmt=True)
    respuesta["Accept-Ranges"] = "bytes"
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


@require_http_methods(["GET"])
def mi_ip(request):
    """Muestra la IP con la que el servidor ve a quien entra. Sirve para habilitar el panel."""
    from .seguridad import ip_cliente

    return render(request, "web/mi_ip.html", {"ip": ip_cliente(request)})


# --------------------------------------------------------------- gestión de contenido

@staff_member_required
@require_http_methods(["GET", "POST"])
def gestion_publicaciones(request):
    """Panel propio para revisar, aprobar y descartar las tarjetas de Instagram."""
    from . import analitica_ig
    from .models import Publicacion
    from .publicaciones import programar, publicar

    if request.method == "POST":
        accion = request.POST.get("accion", "")
        pk = request.POST.get("pk")
        publicacion = Publicacion.objects.filter(pk=pk).first()
        if not publicacion:
            messages.error(request, "No encontramos esa publicación.")
            return redirect("gestion_publicaciones")

        if accion == "aprobar":
            dias = int(request.POST.get("dias") or 1)
            programar(publicacion, dias=dias)
            messages.success(request, f"«{publicacion.nombre}» queda para publicar en {dias} día(s).")
        elif accion == "publicar":
            publicar(publicacion)
            if publicacion.estado == "publicada":
                messages.success(request, f"Publicado: {publicacion.permalink}")
            else:
                messages.error(request, f"No se pudo publicar: {publicacion.error}")
        elif accion == "descartar":
            publicacion.estado = "descartada"
            publicacion.save(update_fields=["estado", "actualizado"])
            messages.warning(request, f"«{publicacion.nombre}» descartada.")
        elif accion == "borrador":
            publicacion.estado = "borrador"
            publicacion.programada = None
            publicacion.save(update_fields=["estado", "programada", "actualizado"])
            messages.info(request, f"«{publicacion.nombre}» vuelve a borrador.")
        return redirect(f"{reverse('gestion_publicaciones')}?estado={request.POST.get('volver', 'borrador')}")

    estado = request.GET.get("estado", "borrador")
    if estado not in ("borrador", "aprobada", "publicada", "descartada", "error"):
        estado = "borrador"

    tarjetas = []
    for publicacion in Publicacion.objects.filter(estado=estado):
        otra, valor = analitica_ig.parecido(publicacion)
        tarjetas.append({"p": publicacion, "parecido": valor,
                         "parecido_con": otra.nombre if otra else ""})

    conteos = {clave: Publicacion.objects.filter(estado=clave).count() for clave in
               ("borrador", "aprobada", "publicada", "descartada")}
    return render(request, "web/gestion_publicaciones.html", {
        "tarjetas": tarjetas, "estado": estado, "conteos": conteos,
        "total": sum(conteos.values()),
    })


@staff_member_required
@require_http_methods(["GET", "POST"])
def gestion(request):
    """Panel único de administración: Instagram, cola de informes y estado del sistema."""
    import re
    from pathlib import Path

    from django.conf import settings as cfg

    from diagnostico.models import Diagnostico
    from red.models import Profesional
    from reports.models import InformeEnCola

    from . import analitica_ig, instagram
    from .metricas import resumen as resumen_metricas
    from .models import Arrepentimiento, EmailSecuencia, Lead, Publicacion

    carpeta = Path(cfg.MEDIA_ROOT) / "publicaciones"

    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "historia":
            archivo = request.POST.get("archivo", "")
            if not re.match(r"^historia-[a-z0-9-]{2,40}$", archivo):
                messages.error(request, "Nombre de historia inválido.")
            else:
                ruta_archivo = carpeta / f"{archivo}.jpg"
                version = int(ruta_archivo.stat().st_mtime) if ruta_archivo.exists() else 0
                url = f"https://{cfg.SITE_DOMAIN}/ig/{archivo}.jpg?v={version}"
                try:
                    contenedor = instagram.crear_contenedor(url, "", tipo="STORIES")
                    instagram.esperar_listo(contenedor)
                    instagram.publicar(contenedor)
                    messages.success(request, f"Historia publicada: {archivo}.")
                except instagram.InstagramError as exc:
                    messages.error(request, f"No se pudo publicar: {exc}")
            return redirect("gestion")

    # La versión sale del mtime: así el panel no muestra una imagen vieja por caché.
    historias = [{"nombre": p.stem, "version": int(p.stat().st_mtime)}
                 for p in sorted(carpeta.glob("historia-*.jpg"))]
    portadas = [{"nombre": p.stem, "version": int(p.stat().st_mtime)}
                for p in sorted(carpeta.glob("portada-*.jpg"))]

    publicadas = Publicacion.objects.filter(estado="publicada").order_by("-publicada_en")[:8]
    cola = Publicacion.objects.filter(estado="aprobada").order_by("programada")[:5]

    return render(request, "web/gestion.html", {
        "conteos": {
            "borrador": Publicacion.objects.filter(estado="borrador").count(),
            "aprobada": Publicacion.objects.filter(estado="aprobada").count(),
            "publicada": Publicacion.objects.filter(estado="publicada").count(),
            "descartada": Publicacion.objects.filter(estado="descartada").count(),
        },
        "publicadas": publicadas,
        "cola": cola,
        "historias": historias,
        "portadas": portadas,
        "ig": analitica_ig.resumen(),
        "m": resumen_metricas(),
        "informes_cola": InformeEnCola.objects.filter(estado="pendiente").count(),
        "profesionales_pendientes": Profesional.objects.filter(estado="pendiente").count(),
        "diagnosticos_7d": Diagnostico.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)).count(),
        "leads": Lead.objects.count(),
        "secuencia_pendiente": EmailSecuencia.objects.filter(enviado=False).count(),
        "arrepentimientos": Arrepentimiento.objects.filter(estado="recibida").count(),
        "ip": request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR", ""),
        "token_ig": bool(getattr(cfg, "IG_TOKEN", "") or __import__("os").environ.get("IG_TOKEN")),
    })


# ------------------------------------------------------- botón de arrepentimiento

def _codigo_arrepentimiento():
    import secrets

    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "AR-" + "".join(secrets.choice(alfabeto) for _ in range(6))


def arrepentimiento(request):
    """Formulario del botón de arrepentimiento (Res. 424/2020, art. 34 Ley 24.240).

    Registra el pedido siempre y manda dos correos: acuse a la persona y aviso
    interno. Si el envío falla, la constancia queda igual.
    """
    from django.conf import settings as cfg
    from django.core.cache import cache
    from django.core.mail import send_mail
    from django.utils import timezone as tz

    from .models import Arrepentimiento

    if request.method == "POST":
        # Trampa para robots: el campo va oculto y una persona no lo ve.
        if (request.POST.get("empresa") or "").strip():
            return render(request, "web/arrepentimiento_ok.html", {"codigo": "AR-RECIBIDO"})

        email = (request.POST.get("email") or "").strip().lower()
        nombre = (request.POST.get("nombre") or "").strip()[:120]
        detalle = (request.POST.get("detalle") or "").strip()[:2000]

        clave = f"arrepentimiento:{email}"
        intentos = cache.get(clave, 0)
        if intentos >= 3:
            messages.error(request, "Ya recibimos varios pedidos con ese correo. "
                                    "Escríbanos directamente y lo resolvemos.")
            return redirect("arrepentimiento")
        if not email or "@" not in email:
            messages.error(request, "Necesitamos el correo con el que contrató, para poder ubicar la cuenta.")
            return render(request, "web/arrepentimiento.html", {"email": email, "nombre": nombre,
                                                                "detalle": detalle})

        solicitud = Arrepentimiento.objects.create(
            codigo=_codigo_arrepentimiento(), email=email, nombre=nombre, detalle=detalle)
        cache.set(clave, intentos + 1, 3600)

        texto = (
            f"Recibimos su pedido de arrepentimiento.\n\n"
            f"Código: {solicitud.codigo}\n"
            f"Fecha de recepción: {tz.localtime(solicitud.creada):%d/%m/%Y %H:%M}\n\n"
            "Usted revocó la contratación dentro de los diez días corridos, sin costo y sin "
            "expresión de causa, conforme al artículo 34 de la Ley 24.240 y la Resolución "
            "424/2020. Damos de baja la suscripción y reintegramos el importe total por el mismo "
            "medio de pago.\n\n"
            "Le confirmamos la baja y el reintegro dentro de los diez días hábiles. Guarde este "
            "código: es la constancia de que el pedido entró.\n\n"
            f"Si necesita algo más, responda este correo o escriba a {cfg.CONTACT_EMAIL}.\n"
        )
        try:
            send_mail(f"Recibimos su pedido de arrepentimiento · {solicitud.codigo}",
                      texto, cfg.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
        except Exception:  # el pedido ya está registrado: el correo no lo condiciona
            logger.exception("No se pudo enviar el acuse de arrepentimiento %s", solicitud.codigo)

        try:
            send_mail(f"[Onto] Arrepentimiento {solicitud.codigo} · {email}",
                      f"Solicitud registrada el {tz.localtime(solicitud.creada):%d/%m/%Y %H:%M}.\n"
                      f"Correo de la cuenta: {email}\n"
                      f"Nombre: {nombre or '(no indicado)'}\n\n"
                      f"Detalle:\n{detalle or '(sin detalle)'}\n\n"
                      f"Responder dentro de los diez días hábiles. Panel: /admin/web/arrepentimiento/\n",
                      cfg.DEFAULT_FROM_EMAIL, [cfg.CONTACT_EMAIL], fail_silently=True)
        except Exception:
            logger.exception("No se pudo avisar internamente el arrepentimiento %s", solicitud.codigo)

        return render(request, "web/arrepentimiento_ok.html", {"codigo": solicitud.codigo,
                                                               "email": email})

    return render(request, "web/arrepentimiento.html")


# ------------------------------------------- autorización de una IP nueva del panel

def _ip_sesion(request):
    from .seguridad import ip_cliente

    return ip_cliente(request)


@login_required
def portal_ip(request):
    """Pantalla que ve el administrador cuando entra desde una conexión no autorizada.

    No habilita nada por sí sola: manda un enlace firmado al correo de contacto.
    Quien abre ese enlace, autoriza.
    """
    from django.conf import settings as cfg
    from django.core import signing
    from django.core.mail import send_mail

    from .seguridad import es_administrador, ip_permitida

    if not es_administrador(request.user):
        raise Http404

    ip = _ip_sesion(request)
    destino = request.GET.get("next") or "/gestion/"
    permitidas = list(getattr(cfg, "ADMIN_IPS", []))
    from .seguridad import ips_autorizadas

    permitidas += ips_autorizadas()
    ya_esta = ip_permitida(ip, permitidas)

    if request.method == "POST":
        token = signing.dumps({"ip": ip, "por": request.user.email}, salt="ip-panel")
        enlace = request.build_absolute_uri(f"/seguridad/ip/{token}/")
        cuerpo = (
            f"Se pidió autorizar una conexión nueva al panel de {cfg.SITE_NAME}.\n\n"
            f"IP: {ip}\n"
            f"Pedido por: {request.user.email}\n"
            f"Navegador: {request.META.get('HTTP_USER_AGENT', '')[:160]}\n\n"
            "Si es usted, abra este enlace para habilitar esa conexión por una hora:\n"
            f"{enlace}\n\n"
            "El enlace vence en una hora y sirve una sola vez. Si no reconoce el pedido, "
            "ignórelo: sin abrirlo, la IP sigue bloqueada.\n"
        )
        try:
            send_mail(f"[Onto] Autorizar conexión desde {ip}", cuerpo,
                      cfg.DEFAULT_FROM_EMAIL, [cfg.CONTACT_EMAIL], fail_silently=False)
            messages.success(request, f"Le enviamos un correo a {cfg.CONTACT_EMAIL} para "
                                      "autorizar esta conexión.")
        except Exception:
            logger.exception("No se pudo enviar el pedido de autorización de IP")
            messages.error(request, "No pudimos enviar el correo. Revise el correo del sistema "
                                    "o pida la IP por otro canal.")
        return redirect(f"/seguridad/ip/?next={destino}")

    return render(request, "web/portal_ip.html", {"ip": ip, "next": destino, "ya_esta": ya_esta})


def confirmar_ip(request, token):
    """Abre el enlace del correo y autoriza la IP. No requiere sesión."""
    from django.core import signing
    from django.core.cache import cache

    from .models import IPAutorizada

    try:
        datos = signing.loads(token, salt="ip-panel", max_age=3600)
    except signing.BadSignature:
        return render(request, "web/portal_ip_error.html", status=410)

    ip = datos.get("ip", "")
    if not ip:
        return render(request, "web/portal_ip_error.html", status=410)
    IPAutorizada.objects.get_or_create(ip=ip, defaults={"nota": f"por {datos.get('por', '')}"[:120]})
    cache.delete("ips_autorizadas")
    messages.success(request, f"La conexión {ip} quedó autorizada. Ya puede usar el panel.")
    return redirect("/gestion/")
