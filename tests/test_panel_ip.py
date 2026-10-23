"""El panel solo existe para las IP habilitadas; sin lista, para nadie."""
from django.test import Client, TestCase, override_settings


class PanelPorIPTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_sin_lista_el_panel_no_existe(self):
        with override_settings(ADMIN_IPS=[]):
            for ruta in ("/admin/", "/metricas/", "/seguridad/2fa/"):
                respuesta = self.client.get(ruta)
                self.assertEqual(respuesta.status_code, 404, ruta)

    def test_el_sitio_publico_sigue_abierto(self):
        with override_settings(ADMIN_IPS=[]):
            self.assertEqual(self.client.get("/").status_code, 200)
            self.assertEqual(self.client.get("/precios/").status_code, 200)
            self.assertEqual(self.client.get("/diagnostico/").status_code, 200)

    def test_ip_habilitada_pasa_el_filtro(self):
        with override_settings(ADMIN_IPS=["10.0.0.5"]):
            respuesta = self.client.get("/admin/", REMOTE_ADDR="10.0.0.5")
            self.assertEqual(respuesta.status_code, 302)
            self.assertIn("/admin/login", respuesta["Location"])

    def test_ip_no_habilitada_no_pasa(self):
        with override_settings(ADMIN_IPS=["10.0.0.5"]):
            self.assertEqual(
                self.client.get("/admin/", REMOTE_ADDR="10.0.0.9").status_code, 404)

    def test_rango_cidr(self):
        with override_settings(ADMIN_IPS=["10.0.0.0/24"]):
            self.assertEqual(
                self.client.get("/admin/", REMOTE_ADDR="10.0.0.77").status_code, 302)
            self.assertEqual(
                self.client.get("/admin/", REMOTE_ADDR="10.0.1.1").status_code, 404)

    def test_respeta_cloudflare(self):
        with override_settings(ADMIN_IPS=["190.10.20.30"]):
            respuesta = self.client.get("/admin/", REMOTE_ADDR="172.18.0.1",
                                        HTTP_CF_CONNECTING_IP="190.10.20.30")
            self.assertEqual(respuesta.status_code, 302)

    def test_varias_ips_separadas_por_coma(self):
        with override_settings(ADMIN_IPS=["10.0.0.5", "200.1.2.3"]):
            self.assertEqual(
                self.client.get("/admin/", REMOTE_ADDR="200.1.2.3").status_code, 302)

    def test_pagina_mi_ip(self):
        with override_settings(ADMIN_IPS=[]):
            respuesta = self.client.get("/mi-ip/", REMOTE_ADDR="181.1.2.3")
            self.assertEqual(respuesta.status_code, 200)
            self.assertContains(respuesta, "181.1.2.3")
