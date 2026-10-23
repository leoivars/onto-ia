from django.conf import settings
from django.db import models


class Report(models.Model):
    MOTOR_CHOICES = [
        ("ia", "Motor de IA"),
        ("local", "Motor local (demostración)"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    numero = models.PositiveIntegerField(default=1)
    titulo = models.CharField(max_length=200)
    engine = models.CharField(max_length=10, choices=MOTOR_CHOICES, default="local")
    model_name = models.CharField(max_length=80, blank=True)
    secciones = models.JSONField(default=list)
    cuerpo = models.TextField(blank=True)
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    tokens_cache = models.PositiveIntegerField(default=0, help_text="Entrada leída de caché")
    costo_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-numero",)
        unique_together = ("user", "numero")
        verbose_name = "informe"
        verbose_name_plural = "informes"

    def __str__(self):
        return f"#{self.numero} · {self.user.get_username()} · {self.titulo}"

    @property
    def es_ia(self):
        return self.engine == "ia"


class Feedback(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="feedbacks")
    resonancia = models.PositiveSmallIntegerField(default=3)
    aciertos = models.TextField("Qué le sirvió", blank=True)
    desaciertos = models.TextField("Qué no le representó", blank=True)
    profundizar = models.TextField("Qué quiere profundizar", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "devolución"
        verbose_name_plural = "devoluciones"

    def __str__(self):
        return f"Devolución {self.resonancia}/5 · informe #{self.report.numero}"


class InformeEnCola(models.Model):
    """Pedido de informe que no se pudo generar por falta de créditos de IA.

    Se reintenta solo y se avisa por correo cuando sale. El usuario nunca pierde el pedido.
    """

    ESTADOS = [
        ("pendiente", "En cola"),
        ("listo", "Generado"),
        ("cancelado", "Cancelado"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="informes_en_cola")
    estado = models.CharField(max_length=10, choices=ESTADOS, default="pendiente", db_index=True)
    motivo = models.TextField(blank=True)
    intentos = models.PositiveIntegerField(default=0)
    ultimo_error = models.TextField(blank=True)
    report = models.ForeignKey(Report, null=True, blank=True, on_delete=models.SET_NULL)
    creado = models.DateTimeField(auto_now_add=True)
    procesado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("creado",)
        verbose_name = "informe en cola"
        verbose_name_plural = "informes en cola"

    def __str__(self):
        return f"{self.user} · {self.get_estado_display()}"
