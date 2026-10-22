from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.urls import include, path, reverse_lazy

from web import views as wv
from web import seo

urlpatterns = [
    path("admin/", admin.site.urls),

    path("robots.txt", seo.robots, name="robots"),
    path("sitemap.xml", seo.sitemap, name="sitemap"),

    path("", wv.landing, name="landing"),
    path("precios/", wv.pricing, name="pricing"),
    path("legal/", wv.legal, name="legal"),
    path("registro/", wv.signup, name="signup"),
    path("panel/", wv.dashboard, name="panel"),
    path("cuenta/", wv.account, name="account"),
    path("cuenta/exportar/", wv.export_data, name="export_data"),
    path("cuenta/eliminar/", wv.delete_account, name="delete_account"),
    path("cuenta/canjear/", wv.redeem_code, name="redeem_code"),

    path("ingresar/", auth_views.LoginView.as_view(
        template_name="web/login.html", redirect_authenticated_user=True), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),

    path("recuperar/", auth_views.PasswordResetView.as_view(
        template_name="web/password_reset_form.html",
        email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
        extra_email_context={"contacto": settings.CONTACT_EMAIL},
        success_url=reverse_lazy("password_reset_done")), name="password_reset"),
    path("recuperar/enviado/", auth_views.PasswordResetDoneView.as_view(
        template_name="web/password_reset_done.html"), name="password_reset_done"),
    path("recuperar/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="web/password_reset_confirm.html",
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("recuperar/listo/", auth_views.PasswordResetCompleteView.as_view(
        template_name="web/password_reset_complete.html"), name="password_reset_complete"),

    path("entrevista/", include("intake.urls")),
    path("informes/", include("reports.urls")),
    path("pagos/", include("pagos.urls")),
]
