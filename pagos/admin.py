from django.contrib import admin

from .models import Pago, Suscripcion


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "estado", "monto", "moneda", "proximo_pago", "created_at")
    list_filter = ("estado", "plan")
    search_fields = ("user__email", "preapproval_id")


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("mp_payment_id", "user", "monto", "moneda", "estado", "created_at")
    list_filter = ("estado",)
    search_fields = ("mp_payment_id", "user__email")
