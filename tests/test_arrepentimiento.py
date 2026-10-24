"""Botón de arrepentimiento: formulario, constancia y acuses (Res. 424/2020)."""
from django.core import mail
from django.test import Client, TestCase

from web.models import Arrepentimiento


class ArrepentimientoTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_la_pagina_existe_y_esta_enlazada(self):
        respuesta = self.client.get("/arrepentimiento/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Revocar una contratación")
        # El pie del sitio tiene que llevar al formulario, no a un ancla.
        home = self.client.get("/").content.decode()
        self.assertIn('href="/arrepentimiento/"', home)

    def test_registra_el_pedido_y_manda_dos_correos(self):
        respuesta = self.client.post("/arrepentimiento/", {
            "email": "persona@ejemplo.test",
            "nombre": "Ana Pérez",
            "detalle": "Contraté el plan Profundo el 2 de octubre.",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Arrepentimiento.objects.count(), 1)

        solicitud = Arrepentimiento.objects.get()
        self.assertTrue(solicitud.codigo.startswith("AR-"))
        self.assertContains(respuesta, solicitud.codigo)
        self.assertEqual(len(mail.outbox), 2)

        acuse = next(m for m in mail.outbox if "persona@ejemplo.test" in m.to)
        self.assertIn(solicitud.codigo, acuse.body)
        self.assertIn("Ley 24.240", acuse.body)
        self.assertIn("diez días hábiles", acuse.body)

    def test_sin_correo_no_registra(self):
        self.client.post("/arrepentimiento/", {"email": "", "nombre": "Ana"})
        self.assertEqual(Arrepentimiento.objects.count(), 0)

    def test_el_honeypot_ignora_robots(self):
        respuesta = self.client.post("/arrepentimiento/", {
            "email": "bot@ejemplo.test", "empresa": "spam", "detalle": "compre ya",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Arrepentimiento.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_no_se_puede_inundar_con_el_mismo_correo(self):
        from django.core.cache import cache

        cache.clear()
        for _ in range(4):
            self.client.post("/arrepentimiento/", {"email": "insistente@ejemplo.test"})
        self.assertEqual(Arrepentimiento.objects.filter(email="insistente@ejemplo.test").count(), 3)
        cache.clear()

    def test_el_texto_legal_enlaza_el_formulario(self):
        html = self.client.get("/legal/").content.decode()
        self.assertIn("formulario del botón de arrepentimiento", html)
        self.assertIn('href="/arrepentimiento/"', html)
