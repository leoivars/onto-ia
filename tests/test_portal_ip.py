"""Autorización de una IP nueva del panel por enlace de correo."""
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.test import Client, TestCase, override_settings

from web.models import IPAutorizada

CLAVE = "Mendoza2026!"


@override_settings(ADMIN_IPS=["10.0.0.1"])
class PortalIPTest(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # la lista de IPs se cachea 30 s entre pedidos
        self.staff = get_user_model().objects.create_user(
            "jefe", email="jefe@ejemplo.test", password=CLAVE, is_staff=True)
        self.client = Client()

    def _entrar(self, otp=True):
        self.client.force_login(self.staff)
        if otp:
            sesion = self.client.session
            sesion["otp_ok"] = True
            sesion.save()

    def test_al_administrador_le_ofrece_autorizar(self):
        self._entrar()
        respuesta = self.client.get("/gestion/", HTTP_X_REAL_IP="200.1.2.3")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/seguridad/ip/", respuesta["Location"])

    def test_al_anonimo_le_sigue_diciendo_que_no_existe(self):
        respuesta = self.client.get("/gestion/", HTTP_X_REAL_IP="200.1.2.3")
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotIn("autorizada", respuesta.content.decode())

    def test_el_portal_muestra_la_ip(self):
        self._entrar()
        respuesta = self.client.get("/seguridad/ip/", HTTP_X_REAL_IP="200.1.2.3")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "200.1.2.3")

    def test_pedir_el_enlace_manda_un_correo(self):
        self._entrar()
        respuesta = self.client.post("/seguridad/ip/", HTTP_X_REAL_IP="200.1.2.3")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("200.1.2.3", mail.outbox[0].subject)
        self.assertIn("/seguridad/ip/", mail.outbox[0].body)
        self.assertEqual(IPAutorizada.objects.count(), 0)  # todavía no autoriza nada

    def test_el_enlace_autoriza_la_ip(self):
        self._entrar()
        self.client.post("/seguridad/ip/", HTTP_X_REAL_IP="200.1.2.3")
        self.assertEqual(IPAutorizada.objects.count(), 0)

        token = signing.dumps({"ip": "200.1.2.3", "por": "jefe@ejemplo.test"}, salt="ip-panel")
        respuesta = self.client.get(f"/seguridad/ip/{token}/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(IPAutorizada.objects.filter(ip="200.1.2.3").exists())

        # Y ahora el panel responde desde esa IP.
        self.assertEqual(self.client.get("/gestion/", HTTP_X_REAL_IP="200.1.2.3").status_code, 200)

    def test_un_enlace_manipulado_se_rechaza(self):
        respuesta = self.client.get("/seguridad/ip/abc123/")
        self.assertEqual(respuesta.status_code, 410)
        self.assertEqual(IPAutorizada.objects.count(), 0)

    def test_una_ip_no_autorizada_sigue_bloqueada_sin_enlace(self):
        self._entrar()
        self.client.post("/seguridad/ip/", HTTP_X_REAL_IP="200.1.2.3")
        respuesta = self.client.get("/gestion/", HTTP_X_REAL_IP="200.1.2.3")
        self.assertEqual(respuesta.status_code, 302)  # al portal, no al panel
