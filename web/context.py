from django.conf import settings


def site(request):
    perfil = None
    if request.user.is_authenticated:
        from .models import perfil_de
        perfil = perfil_de(request.user)
    return {
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
        "SITE_DOMAIN": settings.SITE_DOMAIN,
        "CONTACT_EMAIL": settings.CONTACT_EMAIL,
        "perfil": perfil,
        "plan_quota": settings.PLAN_QUOTA,
        "plan_precio": settings.PLAN_PRICE_ARS,
        "pagos_activos": settings.PAGOS_ACTIVOS,
        "modo_beta": settings.MODO_BETA,
    }
