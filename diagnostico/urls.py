from django.urls import path

from . import views

app_name = "diagnostico"

urlpatterns = [
    path("", views.formulario, name="formulario"),
    path("resultado/", views.resultado, name="resultado"),
    path("listo/", views.hecho, name="hecho"),
]
