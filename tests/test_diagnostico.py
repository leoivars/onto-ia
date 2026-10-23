"""Diagnóstico público de 3 minutos: formulario, teaser, correo y límites."""
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase, override_settings

from diagnostico.models import Diagnostico
from web import ayuda

RESPUESTAS = {
    "situacion": "En la reunión de socios mi padre presentó mi trabajo sin nombrarme.",
    "juicio": "Yo soy la que sostiene, no la que pide.",
    "evita": "Pedir una reunión para hablar de mi rol.",
    "silencio": "A mi padre: que estoy cansada de sostener todo sin reconocimiento.",
    "objetivo": "Tener la conversación y salir con una fecha de respuesta.",
}
INFORME = ("## Qué está sosteniendo\n\nTexto de prueba suficientemente largo.\n\n"
           "## Qué le cuesta\n\nMás texto.\n\n## Una acción para esta semana\n\nEscribir la "
           "conversación pendiente.")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DiagnosticoTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_formulario_publico(self):
        respuesta = self.client.get("/diagnostico/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Yo soy el que")
        self.assertEqual(len(respuesta.context["campos"]), 5)

    def test_respuestas_cortas_no_avanzan(self):
        datos = {k: "x" for k in RESPUESTAS}
        respuesta = self.client.post("/diagnostico/", datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Escriba algo más")
        self.assertNotIn("diagnostico", self.client.session)

    def test_teaser_en_pantalla_y_correo_con_informe(self):
        self.client.post("/diagnostico/", RESPUESTAS)
        resultado = self.client.get("/diagnostico/resultado/")
        self.assertEqual(resultado.status_code, 200)
        self.assertContains(resultado, "lo que evita esta semana")
        self.assertContains(resultado, "Yo soy la que sostiene")

        with patch("diagnostico.views.engine.generar", return_value=(INFORME, "local")):
            respuesta = self.client.post("/diagnostico/resultado/", {"email": "leo@ejemplo.test"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Se lo enviamos")
        self.assertEqual(Diagnostico.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("diagnóstico", mail.outbox[0].subject.lower())
        self.assertIn("plan completo", mail.outbox[0].body.lower())
        self.assertTrue(Diagnostico.objects.first().enviado)

    def test_correo_invalido_no_crea(self):
        self.client.post("/diagnostico/", RESPUESTAS)
        respuesta = self.client.post("/diagnostico/resultado/", {"email": "no-es-correo"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Revise el correo")
        self.assertEqual(Diagnostico.objects.count(), 0)

    def test_honeypot_bloquea(self):
        datos = dict(RESPUESTAS)
        datos["empresa"] = "spam"
        self.client.post("/diagnostico/", datos)
        self.assertEqual(Diagnostico.objects.count(), 0)

    def test_limite_por_ip(self):
        self.client.post("/diagnostico/", RESPUESTAS)
        for _ in range(5):
            Diagnostico.objects.create(email="x@ejemplo.test", respuestas={}, ip="127.0.0.1")
        respuesta = self.client.post("/diagnostico/resultado/", {"email": "leo@ejemplo.test"})
        self.assertContains(respuesta, "varios pedidos")
        self.assertEqual(Diagnostico.objects.count(), 5)

    def test_sin_respuestas_previas_redirige(self):
        respuesta = self.client.get("/diagnostico/resultado/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], "/diagnostico/")

    def test_riesgo_corta_el_flujo_y_muestra_lineas(self):
        datos = dict(RESPUESTAS)
        datos["silencio"] = "A mi padre: hay días en que siento que no quiero vivir."
        with patch("diagnostico.engine.generar") as generar:
            respuesta = self.client.post("/diagnostico/", datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "148")
        self.assertContains(respuesta, "911")
        generar.assert_not_called()
        self.assertEqual(Diagnostico.objects.count(), 0)
        self.assertNotIn("diagnostico", self.client.session)

    def test_riesgo_detecta_aunque_falten_acentos(self):

        self.assertEqual(ayuda.detectar("Quiero hacerme una autolesión"), ["autolesion"])
        self.assertEqual(ayuda.detectar("No aguanto más así"), ["no aguanto mas"])
        self.assertEqual(ayuda.detectar("Tengo una reunión difícil"), [])

    def test_pagina_de_ayuda_publica(self):
        respuesta = self.client.get("/ayuda/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "148")
        self.assertContains(respuesta, "0800 345 1435")
        self.assertContains(respuesta, "911")

    def test_landing_enlaza_la_ayuda(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, 'href="/ayuda/"')

    def test_ia_puede_derivar_aunque_no_haya_palabras_clave(self):
        datos = dict(RESPUESTAS)
        datos["situacion"] = "Ya no le encuentro sentido a nada de lo que hago."
        self.client.post("/diagnostico/", datos)
        with patch("diagnostico.engine.ai.disponible", return_value=True), \
             patch("diagnostico.engine.ai.completar", return_value=("RIESGO", {})):
            respuesta = self.client.post(
                "/diagnostico/resultado/", {"email": "leo@ejemplo.test", "nombre": "Leo"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "148")
        self.assertEqual(Diagnostico.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
