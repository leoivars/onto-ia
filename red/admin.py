from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Documento, Evento, Profesional


class DocumentoInline(admin.TabularInline):
    model = Documento
    extra = 0
    readonly_fields = ("subido_en", "ver")
    fields = ("tipo", "archivo", "ver", "subido_en")

    @admin.display(description="descargar")
    def ver(self, obj):
        if not obj.pk:
            return "—"
        return format_html('<a href="/red/documento/{}/">abrir</a>', obj.pk)


class EventoInline(admin.TabularInline):
    model = Evento
    extra = 0
    can_delete = False
    readonly_fields = ("accion", "detalle", "actor", "cuando")
    fields = ("accion", "detalle", "actor", "cuando")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Profesional)
class ProfesionalAdmin(admin.ModelAdmin):
    list_display = ("apellido", "nombre", "provincia", "matricula", "estado", "email_confirmado",
                    "publico_", "vence_en")
    list_filter = ("estado", "provincia", "email_confirmado", "modalidad")
    search_fields = ("apellido", "nombre", "email", "matricula")
    readonly_fields = ("slug", "token", "creado", "actualizado", "verificado_en", "vence_en",
                       "verificado_por")
    inlines = (DocumentoInline, EventoInline)
    actions = ("accion_verificar", "accion_suspender")
    fieldsets = (
        ("Identidad", {"fields": ("nombre", "apellido", "email", "telefono", "slug")}),
        ("Habilitación", {"fields": ("matricula", "provincia", "registro", "titulo",
                                     "universidad", "anio_egreso")}),
        ("Perfil público", {"fields": ("especialidades", "enfoque", "modalidad", "ciudad", "bio")}),
        ("Verificación", {"fields": ("estado", "email_confirmado", "chequeo_identidad",
                                     "chequeo_matricula", "chequeo_seguro", "verificado_en",
                                     "vence_en", "verificado_por", "motivo_rechazo")}),
        ("Declaraciones", {"fields": ("acepta_protocolo", "consentimiento_datos",
                                      "acepta_sin_comision")}),
        ("Interno", {"fields": ("notas_internas", "token", "creado", "actualizado")}),
    )

    @admin.display(description="público", boolean=True)
    def publico_(self, obj):
        return obj.publico

    @admin.action(description="Verificar seleccionados")
    def accion_verificar(self, request, queryset):
        for p in queryset:
            if not (p.chequeo_identidad and p.chequeo_matricula and p.chequeo_seguro):
                self.message_user(
                    request, f"{p}: faltan chequeos marcados (identidad, matrícula y seguro).",
                    messages.ERROR)
                continue
            p.verificar(usuario=request.user)
        self.message_user(request, "Verificación registrada.", messages.SUCCESS)

    @admin.action(description="Suspender seleccionados")
    def accion_suspender(self, request, queryset):
        for p in queryset:
            p.estado = "suspendido"
            p.save(update_fields=["estado", "actualizado"])
            Evento.objects.create(profesional=p, accion="suspendido", actor=request.user)
        self.message_user(request, "Suspendidos.", messages.WARNING)


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("profesional", "tipo", "subido_en")
    list_filter = ("tipo",)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("cuando", "profesional", "accion", "actor")
    list_filter = ("accion",)
    readonly_fields = ("profesional", "accion", "detalle", "actor", "cuando")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
