"""Red de profesionales: alta, verificación y directorio público.

Principio: nadie aparece en el directorio sin matrícula verificada contra el registro
provincial, constancia documental y revisión humana registrada. La verificación no es un
sello de calidad clínica ni implica recomendación: certifica identidad y habilitación legal.
"""

import secrets
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

PROVINCIAS = [
    ("CABA", "Ciudad Autónoma de Buenos Aires"), ("BA", "Buenos Aires"), ("CAT", "Catamarca"),
    ("CHA", "Chaco"), ("CHU", "Chubut"), ("COR", "Córdoba"), ("CRR", "Corrientes"),
    ("ER", "Entre Ríos"), ("FOR", "Formosa"), ("JUJ", "Jujuy"), ("LP", "La Pampa"),
    ("LR", "La Rioja"), ("MZA", "Mendoza"), ("MIS", "Misiones"), ("NQN", "Neuquén"),
    ("RN", "Río Negro"), ("SAL", "Salta"), ("SJ", "San Juan"), ("SL", "San Luis"),
    ("SC", "Santa Cruz"), ("SF", "Santa Fe"), ("SE", "Santiago del Estero"),
    ("TF", "Tierra del Fuego"), ("TUC", "Tucumán"),
]

ESTADOS = [
    ("pendiente", "Pendiente de verificación"),
    ("verificado", "Verificado"),
    ("rechazado", "Rechazado"),
    ("suspendido", "Suspendido"),
]

TIPOS_DOC = [
    ("matricula", "Constancia de matrícula"),
    ("seguro", "Seguro de responsabilidad civil"),
    ("identidad", "Documento de identidad"),
]


def _token():
    return secrets.token_urlsafe(32)


class Profesional(models.Model):
    nombre = models.CharField(max_length=80)
    apellido = models.CharField(max_length=80)
    email = models.EmailField(unique=True)
    telefono = models.CharField(max_length=40, blank=True)
    matricula = models.CharField(max_length=30)
    provincia = models.CharField(max_length=4, choices=PROVINCIAS)
    registro = models.CharField(
        max_length=120, help_text="Colegio o repartición donde está inscripta la matrícula.")
    titulo = models.CharField(max_length=120)
    universidad = models.CharField(max_length=120, blank=True)
    anio_egreso = models.PositiveIntegerField(null=True, blank=True)
    especialidades = models.CharField(
        max_length=200, help_text="Separadas por coma. Ej.: ansiedad, duelo, pareja.")
    enfoque = models.TextField(max_length=1200, help_text="Cómo trabaja, en sus palabras.")
    modalidad = models.CharField(
        max_length=12, choices=[("online", "Online"), ("presencial", "Presencial"),
                                ("ambas", "Online y presencial")], default="online")
    ciudad = models.CharField(max_length=80, blank=True)
    bio = models.TextField(max_length=900, blank=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="pendiente")
    email_confirmado = models.BooleanField(default=False)
    token = models.CharField(max_length=64, default=_token)
    acepta_protocolo = models.BooleanField(default=False)
    consentimiento_datos = models.BooleanField(default=False)
    acepta_sin_comision = models.BooleanField(default=False)
    # Revisión humana
    chequeo_identidad = models.BooleanField(default=False)
    chequeo_matricula = models.BooleanField(default=False)
    chequeo_seguro = models.BooleanField(default=False)
    verificado_en = models.DateField(null=True, blank=True)
    vence_en = models.DateField(null=True, blank=True)
    verificado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="verificaciones")
    motivo_rechazo = models.TextField(blank=True)
    notas_internas = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profesional"
        verbose_name_plural = "profesionales"
        ordering = ("apellido", "nombre")
        constraints = [
            models.UniqueConstraint(fields=["matricula", "provincia"],
                                    name="matricula_unica_por_provincia"),
        ]

    def __str__(self):
        return f"{self.apellido}, {self.nombre} · {self.get_provincia_display()}"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}".strip()

    @property
    def publico(self):
        hoy = timezone.localdate()
        return (self.estado == "verificado" and self.email_confirmado
                and (self.vence_en is None or self.vence_en >= hoy))

    @property
    def vencimiento_proximo(self):
        if not self.vence_en:
            return False
        return (self.vence_en - timezone.localdate()).days <= 30

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f"{self.nombre}-{self.apellido}")[:110] or "profesional"
            candidato, n = base, 2
            while Profesional.objects.filter(slug=candidato).exclude(pk=self.pk).exists():
                candidato = f"{base}-{n}"
                n += 1
            self.slug = candidato
        if self.estado == "verificado" and not self.vence_en:
            self.vence_en = date(timezone.localdate().year + 1,
                                 timezone.localdate().month, timezone.localdate().day)
        super().save(*args, **kwargs)

    def verificar(self, usuario=None):
        hoy = timezone.localdate()
        self.estado = "verificado"
        self.verificado_en = hoy
        self.vence_en = date(hoy.year + 1, hoy.month, hoy.day)
        self.verificado_por = usuario
        self.save()
        Evento.objects.create(profesional=self, accion="verificado", actor=usuario,
                              detalle="Matrícula, identidad y seguro revisados.")

    def rechazar(self, motivo, usuario=None):
        self.estado = "rechazado"
        self.motivo_rechazo = motivo
        self.save(update_fields=["estado", "motivo_rechazo", "actualizado"])
        Evento.objects.create(profesional=self, accion="rechazado", actor=usuario, detalle=motivo)


class Documento(models.Model):
    profesional = models.ForeignKey(Profesional, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=12, choices=TIPOS_DOC)
    archivo = models.FileField(upload_to="red/privado/%Y/%m/")
    subido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        ordering = ("-subido_en",)

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.profesional}"


class Evento(models.Model):
    """Auditoría: toda decisión sobre un legajo queda registrada."""

    profesional = models.ForeignKey(Profesional, on_delete=models.CASCADE, related_name="eventos")
    accion = models.CharField(max_length=40)
    detalle = models.TextField(blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL)
    cuando = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-cuando",)
        verbose_name = "evento de verificación"
        verbose_name_plural = "eventos de verificación"

    def __str__(self):
        return f"{self.accion} · {self.profesional} · {self.cuando:%d/%m/%Y %H:%M}"
