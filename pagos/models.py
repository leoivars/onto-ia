from django.conf import settings
from django.db import models


class Suscripcion(models.Model):
    ESTADOS = [
        ("pending", "Pendiente"),
        ("authorized", "Activa"),
        ("paused", "Pausada"),
        ("cancelled", "Cancelada"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="suscripciones")
    plan = models.CharField(max_length=12)
    preapproval_id = models.CharField(max_length=64, unique=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="pending")
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=6, default="ARS")
    inicio = models.DateField(null=True, blank=True)
    proximo_pago = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "suscripción"
        verbose_name_plural = "suscripciones"

    def __str__(self):
        return f"{self.user} · {self.plan} · {self.estado}"


class Pago(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pagos")
    suscripcion = models.ForeignKey(
        Suscripcion, null=True, blank=True, on_delete=models.SET_NULL, related_name="pagos")
    mp_payment_id = models.CharField(max_length=64, unique=True)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    moneda = models.CharField(max_length=6, default="ARS")
    estado = models.CharField(max_length=30, blank=True)
    fecha = models.DateTimeField(null=True, blank=True)
    crudo = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "pago"
        verbose_name_plural = "pagos"

    def __str__(self):
        return f"{self.mp_payment_id} · {self.monto} {self.moneda} · {self.estado}"
