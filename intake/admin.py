from django.contrib import admin

from .models import Answer


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("user", "key", "updated_at")
    list_filter = ("key",)
    search_fields = ("user__email", "value")
