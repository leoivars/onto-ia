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
