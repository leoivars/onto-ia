import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import engine
from .models import Diagnostico
from web import ayuda

logger = logging.getLogger(__name__)

PREGUNTAS = [
    ("situacion", "¿Qué situación se repite y ya lo tiene cansado?",
     "Un episodio concreto: qué pasó, con quién, cuándo."),
    ("juicio", "Complete: «Yo soy el que…»",
     "La frase que repite sobre usted. Escríbala sin corregirla."),
    ("evita", "¿Qué está evitando hacer esta semana?",
     "Una llamada, una decisión, una conversación."),
    ("silencio", "¿A quién no le puede decir lo que piensa?",
     "Y qué le diría si pudiera."),
    ("objetivo", "¿Qué quiere que sea distinto en 30 días?",
     "En concreto: qué se vería distinto."),
]
CLAVES = [clave for clave, _, _ in PREGUNTAS]
LIMITE_POR_HORA = 5


def _teaser(datos):
    juicio = " ".join(datos.get("juicio", "").split())[:150]
    evita = " ".join(datos.get("evita", "").split())[:150]
    situacion = " ".join(datos.get("situacion", "").split())[:120]
    return (
        f"Lo que usted describe —«{situacion}»— se sostiene en una frase: «{juicio}». "
        f"Y lo que evita esta semana, «{evita}», no es falta de voluntad: es la conducta que "
        f"protege ese juicio."
    )


def _excedido(ip):
    desde = timezone.now() - timedelta(hours=1)
    return Diagnostico.objects.filter(ip=ip, created_at__gte=desde).count() >= LIMITE_POR_HORA


@require_http_methods(["GET", "POST"])
def formulario(request):
    errores, datos = {}, {}
    if request.method == "POST":
        datos = {clave: (request.POST.get(clave) or "").strip()[:1200] for clave in CLAVES}
        errores = {c: "Escriba algo más." for c in CLAVES if len(datos[c]) < 4}
        if not errores and request.POST.get("empresa"):
            return redirect("diagnostico:hecho")
        if not errores and ayuda.detectar(*datos.values()):
            # No se guarda nada ni se genera informe: primero, ayuda.
            return render(request, "diagnostico/riesgo.html", {"lineas": ayuda.LINEAS})
        if not errores:
            request.session["diagnostico"] = datos
            return redirect("diagnostico:resultado")
    campos = [{"clave": c, "titulo": t, "ayuda": a, "valor": datos.get(c, ""),
               "error": errores.get(c, "")} for c, t, a in PREGUNTAS]
    return render(request, "diagnostico/formulario.html", {"campos": campos})


@require_http_methods(["GET", "POST"])
def resultado(request):
    datos = request.session.get("diagnostico")
    if not datos:
        return redirect("diagnostico:formulario")

    error = ""
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        nombre = (request.POST.get("nombre") or "").strip()[:80]
        ip = request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR")
        try:
            validate_email(email)
        except ValidationError:
            error = "Revise el correo."
        if not error and _excedido(ip):
            error = "Recibimos varios pedidos desde esta conexión. Intente más tarde."
        if not error and request.POST.get("empresa"):
            return redirect("diagnostico:hecho")
        if not error and ayuda.detectar(*datos.values()):
            request.session.pop("diagnostico", None)
            return render(request, "diagnostico/riesgo.html", {"lineas": ayuda.LINEAS})

        if not error:
            texto, motor = engine.generar(datos, nombre)
            diagnostico = Diagnostico.objects.create(
                email=email, nombre=nombre, respuestas=datos, teaser=_teaser(datos),
                informe=texto, motor=motor, ip=ip)
            asunto = f"{nombre}, su diagnóstico de Onto" if nombre else "Su diagnóstico de Onto"
            cuerpo = (
                f"{texto.strip()}\n\n"
                f"Si quiere el plan completo de 30 días, con seguimiento semanal:\n"
                f"https://{settings.SITE_DOMAIN}/registro/\n\n"
                f"—\nOnto · Coaching ontológico asistido por IA\n"
                f"Este diagnóstico es una herramienta de reflexión, no un tratamiento ni un "
                f"diagnóstico clínico. No reemplaza la atención de un profesional de la salud "
                f"mental. Para darse de baja de estos correos, responda «baja»."
            )
            try:
                send_mail(asunto, cuerpo, None, [email], fail_silently=False)
                diagnostico.enviado = True
                diagnostico.save(update_fields=["enviado"])
            except Exception:
                logger.exception("No se pudo enviar el diagnóstico a %s", email)
            request.session.pop("diagnostico", None)
            return render(request, "diagnostico/listo.html", {
                "enviado": diagnostico.enviado,
                "informe": texto if not diagnostico.enviado else "",
                "email": email,
            })

    return render(request, "diagnostico/resultado.html", {
        "teaser": _teaser(datos), "error": error, "preguntas": PREGUNTAS,
    })


def hecho(request):
    return render(request, "diagnostico/listo.html", {"enviado": True, "informe": "", "email": ""})
