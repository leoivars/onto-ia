from django.urls import path

from . import views

app_name = "red"

urlpatterns = [
    path("", views.directorio, name="directorio"),
    path("postular/", views.postular, name="postular"),
    path("confirmar/<str:token>/", views.confirmar, name="confirmar"),
    path("documento/<int:pk>/", views.descargar_documento, name="documento"),
    path("<slug:slug>/", views.ficha, name="ficha"),
]
