from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("generar/", views.generar, name="generar"),
    path("<int:pk>/", views.detalle, name="detalle"),
    path("<int:pk>/feedback/", views.feedback, name="feedback"),
    path("<int:pk>/imprimir/", views.imprimir, name="imprimir"),
]
