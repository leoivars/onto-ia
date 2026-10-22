from django.contrib import admin

from .models import InviteCode, Lead, Profile


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
