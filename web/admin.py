from django.contrib import admin, messages
from django.utils.html import format_html

from .models import DispositivoTOTP, InviteCode, Lead, Profile, Publicacion


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "nombre", "plan", "pro_until", "consent_at", "created_at")
    list_filter = ("plan",)
    search_fields = ("user__email", "nombre")


@admin.register(InviteCode)
class InviteCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "plan", "dias", "used_by", "used_at", "created_at")
    list_filter = ("plan",)
    search_fields = ("code",)


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("email", "origen", "created_at")
    search_fields = ("email",)


@admin.register(Publicacion)
class PublicacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "estado", "programada", "repite", "vista_previa", "publicada_en",
                    "permalink")
    list_filter = ("estado",)
    search_fields = ("nombre", "texto", "caption")
    readonly_fields = ("ig_id", "permalink", "error", "publicada_en", "creado", "actualizado",
                       "vista_previa", "repite")
    actions = ("aprobar_manana", "aprobar_manana_tarde", "publicar_ahora", "descartar")
    fieldsets = (
        ("Contenido", {"fields": ("nombre", "texto", "caption", "pie", "vista_previa", "repite")}),
        ("Estado", {"fields": ("estado", "programada", "publicada_en", "permalink", "ig_id",
                               "error", "creado", "actualizado")}),
    )

    @admin.display(description="parecido con lo ya publicado")
    def repite(self, obj):
        if not obj.pk:
            return "—"
        from .analitica_ig import parecido

        otra, valor = parecido(obj)
        texto = f"{valor:.0%}"
        if valor >= 0.6:
            return format_html('<span style="color:#a33">se repite {} con «{}»</span>',
                               texto, otra.nombre)
        if valor >= 0.35:
            return format_html('<span style="color:#a70">se parece {} a «{}»</span>',
                               texto, otra.nombre)
        return "distinto"

    @admin.display(description="tarjeta")
    def vista_previa(self, obj):
        if not obj.pk:
            return "—"
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" style="max-width:340px;border:1px solid '
            '#ddd"></a>', obj.imagen_url, obj.imagen_url)

    def _aprobar(self, request, queryset, dias):
        from .publicaciones import programar

        for publicacion in queryset:
            if publicacion.estado in ("publicada", "descartada"):
                continue
            programar(publicacion, dias=dias)
        self.message_user(request, f"Aprobadas para publicar en {dias} día(s).", messages.SUCCESS)

    @admin.action(description="Aprobar y publicar mañana 10:00")
    def aprobar_manana(self, request, queryset):
        self._aprobar(request, queryset, 1)

    @admin.action(description="Aprobar y publicar en 2 días 10:00")
    def aprobar_manana_tarde(self, request, queryset):
        self._aprobar(request, queryset, 2)

    @admin.action(description="Publicar ahora")
    def publicar_ahora(self, request, queryset):
        from .publicaciones import publicar

        for publicacion in queryset:
            publicar(publicacion)
            if publicacion.estado == "error":
                self.message_user(request, f"{publicacion.nombre}: {publicacion.error}",
                                  messages.ERROR)
        self.message_user(request, "Publicación ejecutada.", messages.SUCCESS)

    @admin.action(description="Descartar")
    def descartar(self, request, queryset):
        queryset.update(estado="descartada")


@admin.register(DispositivoTOTP)
class DispositivoTOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "activo", "creado", "ultimo_uso", "respaldos")
    readonly_fields = ("user", "secreto", "confirmado_en", "creado", "ultimo_uso",
                       "codigos_respaldo")
    actions = ("resetear",)

    @admin.display(description="activo", boolean=True)
    def activo(self, obj):
        return bool(obj.confirmado_en)

    @admin.display(description="respaldos restantes")
    def respaldos(self, obj):
        return len(obj.codigos_respaldo or [])

    @admin.action(description="Resetear el segundo factor (obliga a configurarlo de nuevo)")
    def resetear(self, request, queryset):
        for dispositivo in queryset:
            DispositivoTOTP.objects.filter(pk=dispositivo.pk).delete()
        self.message_user(request, "Reseteado: esos usuarios deberán configurarlo al entrar.",
                          messages.WARNING)
