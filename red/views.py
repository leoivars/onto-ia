import logging

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import PostulacionForm
from .models import Documento, Evento, Profesional

logger = logging.getLogger(__name__)
LIMITE_POR_HORA = 3


def _excedido(request):
    clave = "postulaciones"
    ahora = timezone.now().timestamp()
    marcas = [m for m in request.session.get(clave, []) if ahora - m < 3600]
    request.session[clave] = marcas + [ahora]
    return len(marcas) >= LIMITE_POR_HORA


@require_http_methods(["GET", "POST"])
def postular(request):
    form = PostulacionForm(request.POST or None, request.FILES or None)
    enviado = False
    if request.method == "POST":
        if request.POST.get("empresa"):
            return render(request, "red/gracias.html", {"enviado": True})
        if _excedido(request):
            form.add_error(None, "Recibimos varias postulaciones desde esta conexión. "
                                 f"Escríbanos a {settings.CONTACT_EMAIL} y lo resolvemos a mano.")
        elif form.is_valid():
            profesional = form.save(commit=False)
            profesional.estado = "pendiente"
            profesional.save()
            for campo, tipo in (("constancia_matricula", "matricula"), ("seguro", "seguro"),
                                ("identidad", "identidad")):
                archivo = form.cleaned_data.get(campo)
                if archivo:
                    Documento.objects.create(profesional=profesional, tipo=tipo, archivo=archivo)
            Evento.objects.create(profesional=profesional, accion="postulacion",
                                  detalle="Alta desde el formulario público.")
            _enviar_confirmacion(profesional)
            enviado = True
            return render(request, "red/gracias.html", {"enviado": True})
    return render(request, "red/postular.html", {"form": form, "enviado": enviado})


def _enviar_confirmacion(profesional):
    enlace = f"https://{settings.SITE_DOMAIN}/red/confirmar/{profesional.token}/"
    cuerpo = (
        f"{profesional.nombre}, recibimos su postulación a la red de Onto.\n\n"
        f"Para continuar con la verificación, confirme este correo:\n{enlace}\n\n"
        f"Después revisamos la constancia de matrícula contra el registro provincial y la póliza "
        f"de seguro. Le escribimos con la decisión.\n\n"
        f"—\nOnto · Red de profesionales"
    )
    try:
        send_mail("Confirme su correo · Red de Onto", cuerpo, None, [profesional.email])
    except Exception:
        logger.exception("No se pudo enviar la confirmación a %s", profesional.email)


@require_http_methods(["GET"])
def confirmar(request, token):
    profesional = Profesional.objects.filter(token=token).first()
    if not profesional:
        raise Http404
    if not profesional.email_confirmado:
        profesional.email_confirmado = True
        profesional.save(update_fields=["email_confirmado", "actualizado"])
        Evento.objects.create(profesional=profesional, accion="email_confirmado")
    return render(request, "red/confirmado.html", {"profesional": profesional})


def directorio(request):
    profesionales = [p for p in Profesional.objects.filter(estado="verificado",
                                                           email_confirmado=True)
                     if p.publico]
    provincias = {}
    for p in profesionales:
        provincias.setdefault(p.get_provincia_display(), []).append(p)
    return render(request, "red/directorio.html", {
        "provincias": dict(sorted(provincias.items())), "total": len(profesionales)})


def ficha(request, slug):
    profesional = get_object_or_404(Profesional, slug=slug)
    if not profesional.publico:
        raise Http404
    return render(request, "red/ficha.html", {"p": profesional})


@staff_member_required
def descargar_documento(request, pk):
    documento = get_object_or_404(Documento, pk=pk)
    try:
        return FileResponse(documento.archivo.open("rb"),
                            as_attachment=True,
                            filename=f"{documento.tipo}-{documento.profesional.slug}.pdf")
    except FileNotFoundError:
        raise Http404
