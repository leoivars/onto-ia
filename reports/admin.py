from django.contrib import admin

from .models import Feedback, Report


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
