"""Flujo completo: registro, entrevista, informe, cuota, canje, feedback, exportación y borrado."""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from intake import questions as Q
from reports.models import Report
from web.models import InviteCode, Lead

EMAIL = "persona@ejemplo.test"
PASSWORD = "Mendoza2026!"


def cargar_entrevista(client):
    for bloque in Q.BLOCKS:
        datos = {q["key"]: f"Respuesta de prueba sobre {q['label']}."
                 for q in bloque["questions"]}
        respuesta = client.post(f"/entrevista/{bloque['slug']}/", datos)
        assert respuesta.status_code == 302, bloque["slug"]


class FlujoCompletoTest(TestCase):
    def setUp(self):
        self.client = Client()
        respuesta = self.client.post("/registro/", {
            "nombre": "Leo",
            "email": EMAIL,
            "password1": PASSWORD,
            "password2": PASSWORD,
            "consent": "on",
        }, follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.user = get_user_model().objects.get(email=EMAIL)
        self.client.force_login(self.user)

    def test_paginas_publicas(self):
        publico = Client()
        for url in ["/", "/precios/", "/legal/", "/registro/", "/ingresar/"]:
            self.assertEqual(publico.get(url).status_code, 200, url)

    def test_seo(self):
        publico = Client()
        respuesta = publico.get("/")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn('rel="canonical"', html)
        self.assertIn('application/ld+json', html)
        self.assertEqual(publico.get("/robots.txt").status_code, 200)
        self.assertEqual(publico.get("/sitemap.xml").status_code, 200)
        self.assertIn("Sitemap:", publico.get("/robots.txt").content.decode())

        privada = publico.get("/ingresar/").content.decode()
        self.assertIn("noindex", privada)

    @override_settings(ALLOWED_HOSTS=["onto.zx.com.ar"])
    def test_host_no_permitido(self):
        ajeno = Client(SERVER_NAME="otro.example")
        self.assertEqual(ajeno.get("/").status_code, 400)

    def test_entrevista_y_progreso(self):
        cargar_entrevista(self.client)
        respondidas, total, pct = Q.progress(self.user)
        self.assertEqual((respondidas, total, pct), (Q.TOTAL, Q.TOTAL, 100))

    def test_informe_local(self):
        cargar_entrevista(self.client)
        respuesta = self.client.post("/informes/generar/", follow=True)
        self.assertEqual(respuesta.status_code, 200)

        informe = Report.objects.get(user=self.user)
        self.assertEqual(informe.engine, "local")
        self.assertEqual(len(informe.secciones), 9)
        titulos = [s["titulo"] for s in informe.secciones]
        self.assertIn("Plan de 30 días", titulos)
        self.assertGreater(sum(len(s["cuerpo"].split()) for s in informe.secciones), 600)

    def test_cuota_gratuita_bloquea_el_segundo(self):
        cargar_entrevista(self.client)
        self.client.post("/informes/generar/", follow=True)
        respuesta = self.client.post("/informes/generar/", follow=True)
        self.assertEqual(Report.objects.filter(user=self.user).count(), 1)
        self.assertIn("/precios/", respuesta.redirect_chain[-1][0])

    def test_canjear_codigo_y_profundizar(self):
        cargar_entrevista(self.client)
        informe = self.client.post("/informes/generar/", follow=True)
        primero = Report.objects.get(user=self.user)

        self.client.post(f"/informes/{primero.pk}/feedback/", {
            "resonancia": "2",
            "aciertos": "La distinción juicio/hecho.",
            "desaciertos": "El plan de 30 días.",
            "profundizar": "El vínculo con mi padre.",
        })

        InviteCode.objects.create(code="OBS-TEST-30", plan="pro", dias=30)
        self.client.post("/cuenta/canjear/", {"code": "obs-test-30"}, follow=True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.plan_efectivo, "pro")

        self.client.post("/informes/generar/", follow=True)
        segundo = Report.objects.filter(user=self.user).order_by("-numero").first()
        self.assertEqual(segundo.numero, 2)
        titulos = [s["titulo"] for s in segundo.secciones]
        self.assertIn("Ajustes sobre el informe anterior", titulos)

    def test_exportar_y_eliminar(self):
        cargar_entrevista(self.client)
        self.client.post("/informes/generar/", follow=True)

        respuesta = self.client.get("/cuenta/exportar/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Disposition"].split(";")[0], "attachment")
        datos = json.loads(respuesta.content)
        self.assertEqual(len(datos["respuestas"]), Q.TOTAL)
        self.assertEqual(len(datos["informes"]), 1)

        self.client.post("/cuenta/eliminar/", follow=True)
        self.assertFalse(get_user_model().objects.filter(email=EMAIL).exists())
        self.assertEqual(Report.objects.count(), 0)

    def test_lead_desde_precios(self):
        anonimo = Client()
        anonimo.post("/precios/", {"email": "espera@ejemplo.test"})
        self.assertTrue(Lead.objects.filter(email="espera@ejemplo.test").exists())
