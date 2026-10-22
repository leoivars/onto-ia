from django.urls import path

from . import views

app_name = "pagos"

urlpatterns = [
    path("suscribirse/<str:plan>/", views.suscribirse, name="suscribirse"),
    path("retorno/", views.retorno, name="retorno"),
    path("estado/", views.estado, name="estado"),
    path("cancelar/<int:pk>/", views.cancelar, name="cancelar"),
    path("webhook/", views.webhook, name="webhook"),
]
