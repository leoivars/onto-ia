from datetime import date

from django.conf import settings
from django.db import models


class Profile(models.Model):
    FREE, PRO, ESTUDIO = "free", "pro", "estudio"
    PLAN_CHOICES = [
        (FREE, "Gratuito"),
        (PRO, "Profundo"),
        (ESTUDIO, "Estudio"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    nombre = models.CharField("¿Cómo prefiere que lo llamemos?", max_length=120, blank=True)
    consent_at = models.DateTimeField("Consentimiento informado", null=True, blank=True)
    origen = models.CharField(max_length=60, blank=True)
    plan = models.CharField(max_length=12, choices=PLAN_CHOICES, default=FREE)
    pro_until = models.DateField("Acceso hasta", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre or self.user.get_username()} · {self.plan_efectivo}"

    @property
    def plan_efectivo(self):
        if self.plan in (self.PRO, self.ESTUDIO):
            if self.pro_until is None or self.pro_until >= date.today():
                return self.plan
        return self.FREE

    @property
    def es_pago(self):
        return self.plan_efectivo != self.FREE

    @property
    def plan_efectivo_display(self):
        return dict(self.PLAN_CHOICES)[self.plan_efectivo]

    @property
    def cuota_mensual(self):
        return settings.PLAN_QUOTA[self.plan_efectivo]

    def informes_este_mes(self):
        from reports.models import Report
        hoy = date.today()
        return Report.objects.filter(
            user=self.user, created_at__year=hoy.year, created_at__month=hoy.month).count()

    @property
    def informes_disponibles(self):
        return max(0, self.cuota_mensual - self.informes_este_mes())

    @property
    def puede_generar(self):
        return self.informes_disponibles > 0


def perfil_de(user):
    perfil, _ = Profile.objects.get_or_create(user=user)
    return perfil


class InviteCode(models.Model):
    """Acceso anticipado: canjea N días de plan pago sin pasar por checkout."""
    code = models.CharField(max_length=24, unique=True)
    plan = models.CharField(max_length=12, choices=Profile.PLAN_CHOICES, default=Profile.PRO)
    dias = models.PositiveIntegerField(default=30)
    nota = models.CharField(max_length=160, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="codigos_canjeados")
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "código de invitación"
        verbose_name_plural = "códigos de invitación"

    def __str__(self):
        return f"{self.code} ({self.plan}, {self.dias} días)"


class Lead(models.Model):
    """Lista de espera para el lanzamiento comercial."""
    email = models.EmailField(unique=True)
    origen = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class Visita(models.Model):
    """Vista de página sin datos personales: sirve para medir el embudo."""

    ruta = models.CharField(max_length=120, db_index=True)
    referente = models.CharField(max_length=200, blank=True)
    origen = models.CharField(max_length=60, blank=True, db_index=True)
    fuente = models.CharField(max_length=60, blank=True)
    medio = models.CharField(max_length=60, blank=True)
    campana = models.CharField(max_length=60, blank=True)
    sesion = models.CharField(max_length=32, db_index=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="visitas")
    creada = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-creada",)
        verbose_name = "visita"
        verbose_name_plural = "visitas"

    def __str__(self):
        return f"{self.ruta} · {self.origen or 'directo'}"


class OptOut(models.Model):
    """Correo que pidió no recibir más mensajes. Se respeta en toda la secuencia."""

    email = models.EmailField(unique=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "baja de correos"
        verbose_name_plural = "bajas de correos"

    def __str__(self):
        return self.email


class EmailSecuencia(models.Model):
    """Un correo programado de la secuencia posterior al diagnóstico."""

    email = models.EmailField(db_index=True)
    paso = models.PositiveSmallIntegerField()
    asunto = models.CharField(max_length=200)
    cuerpo = models.TextField()
    programado = models.DateTimeField(db_index=True)
    enviado = models.BooleanField(default=False, db_index=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("programado",)
        verbose_name = "correo de secuencia"
        verbose_name_plural = "correos de secuencia"
        constraints = [
            models.UniqueConstraint(fields=["email", "paso"], name="un_correo_por_paso"),
        ]

    def __str__(self):
        return f"{self.email} · paso {self.paso}"
