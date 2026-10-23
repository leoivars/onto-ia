from django.contrib import admin

from .models import Diagnostico


@admin.register(Diagnostico)
class DiagnosticoAdmin(admin.ModelAdmin):
    list_display = ("email", "motor", "enviado", "conversion", "created_at")
    list_filter = ("motor", "enviado")
    search_fields = ("email",)
    readonly_fields = ("respuestas", "teaser", "informe")
