from django.conf import settings
from django.db import models


class Answer(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="answers")
    key = models.CharField(max_length=64)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "key")
        ordering = ("key",)
        verbose_name = "respuesta"
        verbose_name_plural = "respuestas"

    def __str__(self):
        return f"{self.key}: {self.value[:60]}"


class Entrevista(models.Model):
    """Una entrevista por persona: guarda la variante del diseño y la ronda adaptativa.

    La variante permite comparar diseños distintos con datos reales: cada informe
    queda etiquetado con el diseño de entrevista que lo originó.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="entrevistas")
    variante = models.CharField(max_length=40, default="adaptativa-v1")
    iniciada = models.DateTimeField(auto_now_add=True)
    completada = models.DateTimeField(null=True, blank=True)
    repreguntas = models.JSONField(default=list, blank=True)
    generadas_en = models.DateTimeField(null=True, blank=True)
    saltada = models.BooleanField(default=False, help_text="La persona decidió no responder la ronda.")
    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    costo_usd = models.DecimalField(max_digits=8, decimal_places=5, default=0)

    class Meta:
        ordering = ("-iniciada",)
        verbose_name = "entrevista"
        verbose_name_plural = "entrevistas"

    def __str__(self):
        return f"Entrevista de {self.user} ({self.variante})"

    @property
    def contestadas(self):
        return sum(1 for r in self.repreguntas if (r.get("respuesta") or "").strip())

    @property
    def tiene_repreguntas(self):
        return bool(self.repreguntas)


class Paso(models.Model):
    """Cuándo se abrió y se guardó cada bloque. Es la materia prima del embudo."""

    entrevista = models.ForeignKey(
        Entrevista, on_delete=models.CASCADE, related_name="pasos")
    slug = models.CharField(max_length=40)
    abierto = models.DateTimeField(auto_now_add=True)
    guardado = models.DateTimeField(null=True, blank=True)
    campos = models.PositiveSmallIntegerField(default=0, help_text="Respuestas no vacías en el bloque.")
    segundos = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("entrevista", "slug")
        ordering = ("abierto",)
        verbose_name = "paso de la entrevista"
        verbose_name_plural = "pasos de la entrevista"

    def __str__(self):
        return f"{self.slug} ({'guardado' if self.guardado else 'abierto'})"
