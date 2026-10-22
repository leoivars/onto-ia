from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

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

    path("entrevista/", include("intake.urls")),
    path("informes/", include("reports.urls")),
]
