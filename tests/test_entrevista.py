"""Entrevista adaptativa: repreguntas, embudo por bloque y etiqueta de variante."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from intake import adaptativa
from intake import questions as Q
from intake.models import Answer, Entrevista, Paso
from reports import engine
from reports.models import Report
from web.metricas import embudo_entrevista

CLAVE = "Mendoza2026!"


def usuario(email="entrevista@ejemplo.test"):
    return get_user_model().objects.create_user(email, email=email, password=CLAVE)


def cargar_respuestas(user, bloques=None, largo=400):
    for bloque in Q.BLOCKS:
        if bloques and bloque["slug"] not in bloques:
            continue
        for q in bloque["questions"]:
            Answer.objects.update_or_create(
                user=user, key=q["key"],
                defaults={"value": f"Sobre {q['label']}: " + ("detalle concreto " * (largo // 18))})


RESPUESTA_IA = json.dumps([
    {"key": "jefe-ultima-vez", "pregunta": "¿Qué pasó la última vez que sintió eso?",
     "motivo": "Falta el episodio concreto."},
    {"key": "que-dijo", "pregunta": "¿Qué le dijo exactamente su jefe?",
     "motivo": "La respuesta actual es una interpretación."},
    {"key": "que-hizo", "pregunta": "¿Qué hizo usted después de esa conversación?",
     "motivo": "No hay acciones descritas."},
])


class EntrevistaTest(TestCase):
    def setUp(self):
        self.user = usuario()
        self.client = Client()
        self.client.force_login(self.user)

    # ---------------------------------------------------------------- pasos

    def test_registra_apertura_y_guardado_del_bloque(self):
        bloque = Q.BLOCKS[0]
        self.client.get(f"/entrevista/{bloque['slug']}/")
        paso = Paso.objects.get(entrevista__user=self.user, slug=bloque["slug"])
        self.assertIsNone(paso.guardado)

        datos = {q["key"]: "respuesta" for q in bloque["questions"]}
        self.client.post(f"/entrevista/{bloque['slug']}/", datos)
        paso.refresh_from_db()
        self.assertIsNotNone(paso.guardado)
        self.assertEqual(paso.campos, len(bloque["questions"]))
        self.assertGreaterEqual(paso.segundos, 0)

    def test_el_ultimo_bloque_lleva_a_la_ronda(self):
        for bloque in Q.BLOCKS[:-1]:
            self.client.post(f"/entrevista/{bloque['slug']}/",
                             {q["key"]: "algo" for q in bloque["questions"]})
        ultimo = Q.BLOCKS[-1]
        respuesta = self.client.post(f"/entrevista/{ultimo['slug']}/",
                                     {q["key"]: "algo" for q in ultimo["questions"]})
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/entrevista/repreguntas/", respuesta["Location"])

    # ------------------------------------------------------------ la ronda

    @patch("reports.ai.completar")
    def test_genera_la_ronda_una_sola_vez(self, completar):
        cargar_respuestas(self.user)
        completar.return_value = (RESPUESTA_IA, {"in": 900, "out": 120, "cache": 0})

        respuesta = self.client.get("/entrevista/repreguntas/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "¿Qué pasó la última vez que sintió eso?")

        entrevista = Entrevista.objects.get(user=self.user)
        self.assertEqual(len(entrevista.repreguntas), 3)
        self.assertEqual(entrevista.repreguntas[0]["respuesta"], "")
        self.assertGreater(entrevista.costo_usd, 0)

        self.client.get("/entrevista/repreguntas/")
        self.assertEqual(completar.call_count, 1)

    @patch("reports.ai.completar")
    def test_guardar_respuestas(self, completar):
        cargar_respuestas(self.user)
        completar.return_value = (RESPUESTA_IA, {"in": 900, "out": 120, "cache": 0})
        self.client.get("/entrevista/repreguntas/")

        respuesta = self.client.post("/entrevista/repreguntas/", {
            "jefe-ultima-vez": "Me interrumpió frente a todos.",
            "que-dijo": "Que el informe no servía.",
        })
        self.assertEqual(respuesta.status_code, 302)
        entrevista = Entrevista.objects.get(user=self.user)
        self.assertEqual(entrevista.contestadas, 2)
        self.assertEqual(entrevista.repreguntas[2]["respuesta"], "")

    @patch("reports.ai.completar")
    def test_se_puede_saltear(self, completar):
        cargar_respuestas(self.user)
        completar.return_value = (RESPUESTA_IA, {"in": 900, "out": 120, "cache": 0})
        self.client.get("/entrevista/repreguntas/")

        respuesta = self.client.post("/entrevista/repreguntas/", {"accion": "saltar"})
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Entrevista.objects.get(user=self.user).saltada)

    @patch("intake.adaptativa.ai.disponible", return_value=False)
    def test_sin_motor_no_se_rompe(self, _disponible):
        cargar_respuestas(self.user)
        respuesta = self.client.get("/entrevista/repreguntas/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/entrevista/revision/", respuesta["Location"])

    @patch("reports.ai.completar")
    def test_basura_del_modelo_no_rompe(self, completar):
        cargar_respuestas(self.user)
        completar.return_value = ("No puedo ayudarte con eso.", {"in": 10, "out": 5, "cache": 0})
        respuesta = self.client.get("/entrevista/repreguntas/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Entrevista.objects.get(user=self.user).repreguntas, [])

    # --------------------------------------------------- llegada al informe

    @patch("reports.ai.completar")
    def test_las_respuestas_entran_al_prompt(self, completar):
        cargar_respuestas(self.user)
        completar.return_value = (RESPUESTA_IA, {"in": 900, "out": 120, "cache": 0})
        self.client.get("/entrevista/repreguntas/")
        self.client.post("/entrevista/repreguntas/",
                         {"jefe-ultima-vez": "Me interrumpió frente a todos."})

        ctx = engine.contexto(self.user)
        self.assertIn("Me interrumpió frente a todos.", ctx["repreguntas_texto"])
        self.assertEqual(ctx["variante"], "adaptativa-v1")

    def test_el_informe_guarda_la_variante(self):
        cargar_respuestas(self.user, largo=60)
        entrevista = adaptativa.entrevista_de(self.user)
        self.assertEqual(entrevista.variante, "adaptativa-v1")

        informe = engine.generar(self.user)
        self.assertEqual(informe.variante_entrevista, "adaptativa-v1")
        self.assertIsInstance(informe, Report)

    # -------------------------------------------------------------- embudo

    def test_el_embudo_cuenta_por_bloque(self):
        bloque = Q.BLOCKS[0]
        self.client.get(f"/entrevista/{bloque['slug']}/")
        self.client.post(f"/entrevista/{bloque['slug']}/",
                         {q["key"]: "algo" for q in bloque["questions"]})

        datos = embudo_entrevista()
        self.assertEqual(datos["iniciadas"], 1)
        primero = next(b for b in datos["bloques"] if b["slug"] == bloque["slug"])
        self.assertEqual(primero["abiertos"], 1)
        self.assertEqual(primero["guardados"], 1)
        self.assertEqual(primero["pct"], 100)

    @override_settings(INTAKE_AB="fijo-v1,adaptativa-v1")
    def test_el_reparto_ab_es_estable(self):
        u1, u2 = usuario("a@ejemplo.test"), usuario("b@ejemplo.test")
        primera = adaptativa.variante_para(u1)
        self.assertEqual(primera, adaptativa.variante_para(u1))
        self.assertIn(primera, ("fijo-v1", "adaptativa-v1"))
        self.assertIn(adaptativa.variante_para(u2), ("fijo-v1", "adaptativa-v1"))
