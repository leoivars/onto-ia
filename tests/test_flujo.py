"""Flujo completo: registro, entrevista, informe, cuota, canje, feedback, exportación y borrado."""
import json
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from intake import questions as Q
from intake.models import Answer
from reports.models import Report
from web.models import InviteCode, Lead, perfil_de

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

    @override_settings(ALLOWED_HOSTS=["onto.xz.com.ar"])
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

    def _hacer_pago(self):
        perfil = perfil_de(self.user)
        perfil.plan = "pro"
        perfil.pro_until = date.today() + timedelta(days=30)
        perfil.save()

    def test_segundo_click_no_duplica_el_informe(self):
        self._hacer_pago()
        cargar_entrevista(self.client)
        self.client.post("/informes/generar/", follow=True)
        primero = Report.objects.get(user=self.user)

        respuesta = self.client.post("/informes/generar/", follow=True)
        self.assertEqual(Report.objects.filter(user=self.user).count(), 1)
        self.assertEqual(respuesta.redirect_chain[-1][0], f"/informes/{primero.pk}/")

        self.client.post("/informes/generar/", {"forzar": "1"}, follow=True)
        self.assertEqual(Report.objects.filter(user=self.user).count(), 2)

    def test_cambiar_una_respuesta_habilita_otro_informe(self):
        self._hacer_pago()
        cargar_entrevista(self.client)
        self.client.post("/informes/generar/", follow=True)
        self.assertEqual(Report.objects.filter(user=self.user).count(), 1)

        Answer.objects.filter(user=self.user, key="historia_quiebre").update(
            value="Otro episodio, contado con más detalle.", updated_at=timezone.now())
        self.client.post("/informes/generar/", follow=True)
        self.assertEqual(Report.objects.filter(user=self.user).count(), 2)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_recuperacion_de_contrasena(self):
        from django.core import mail

        self.client.logout()
        respuesta = self.client.post("/recuperar/", {"email": EMAIL})
        self.assertRedirects(respuesta, "/recuperar/enviado/")
        self.assertEqual(len(mail.outbox), 1)

        cuerpo = mail.outbox[0].body
        enlace = next(l.strip() for l in cuerpo.splitlines() if "/recuperar/" in l)
        camino = enlace.replace("http://testserver", "")

        paso = self.client.get(camino, follow=True)
        self.assertEqual(paso.status_code, 200)
        url_form = paso.redirect_chain[-1][0]

        final = self.client.post(url_form, {
            "new_password1": "NuevaClave2026!",
            "new_password2": "NuevaClave2026!",
        }, follow=True)
        self.assertContains(final, "Contraseña actualizada")

        self.client.logout()
        self.assertTrue(self.client.login(username=EMAIL, password="NuevaClave2026!"))
