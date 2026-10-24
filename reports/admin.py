from django.contrib import admin

from .models import AuditoriaIA, Feedback, Report


class FeedbackInline(admin.StackedInline):
    model = Feedback
    extra = 0


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("numero", "user", "engine", "model_name", "tokens_in", "tokens_out",
                    "costo_usd", "created_at")
    list_filter = ("engine", "created_at")
    search_fields = ("user__email", "titulo")
    inlines = [FeedbackInline]
    readonly_fields = ("cuerpo",)


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("report", "resonancia", "created_at")
    list_filter = ("resonancia",)


@admin.register(AuditoriaIA)
class AuditoriaIAAdmin(admin.ModelAdmin):
    """Solo lectura: es una constancia, no un registro editable."""

    list_display = ("cuando", "user", "clase", "modelo", "sustituciones", "caracteres",
                    "tokens_in", "tokens_out")
    list_filter = ("clase", "modelo")
    search_fields = ("user__email", "sha")
    date_hierarchy = "cuando"
    readonly_fields = ("user", "cuando", "modelo", "clase", "sha", "caracteres", "sustituciones",
                       "tokens_in", "tokens_out", "costo")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
