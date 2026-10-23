from django.conf import settings
from django.db import models


class Diagnostico(models.Model):
    email = models.EmailField()
    nombre = models.CharField(max_length=80, blank=True)
    respuestas = models.JSONField(default=dict)
    teaser = models.TextField(blank=True)
    informe = models.TextField(blank=True)
    motor = models.CharField(max_length=10, default="local")
    enviado = models.BooleanField(default=False)
    origen = models.CharField(max_length=60, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "diagnóstico"
        verbose_name_plural = "diagnósticos"

    def __str__(self):
        return f"{self.email} · {self.created_at:%d/%m/%Y %H:%M}"

    @property
    def conversion(self):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.filter(email__iexact=self.email).exists()
