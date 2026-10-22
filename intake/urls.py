from django.urls import path

from . import views

app_name = "intake"

urlpatterns = [
    path("", views.start, name="start"),
    path("revision/", views.revision, name="revision"),
    path("<slug:slug>/", views.step, name="step"),
]
