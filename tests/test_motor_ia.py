"""Camino de IA con un proveedor simulado: no usa claves reales ni red."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from intake import questions as Q
from intake.models import Answer
from reports import ai, engine
from reports.models import Feedback, Report
from web.models import perfil_de

SECCIONES = [
    ("Lectura del observador", "Usted se describe como «el que sostiene». Eso es un juicio."),
    ("El quiebre que lo trajo", "El balance presentado sin su nombre no es la causa."),
    ("Juicios maestros", "Sobre usted, sobre otros y sobre el mundo."),
    ("Lenguaje, emoción y cuerpo", "Bronca contenida, mandíbula apretada."),
    ("Promesas y compromisos", "El torneo de su hija y la conversación con su padre."),
    ("El costo del patrón", "Tres años sin ascenso."),
    ("Declaraciones para una nueva observación", "«Yo, Mariana, declaro...»."),
    ("Plan de 30 días", "- Semana 1: registro de juicios."),
    ("Preguntas para profundizar", "- ¿Qué protege al no decidir?"),
]
RESPUESTA_IA = "\n\n".join(f"## {t}\n\n{c}" for t, c in SECCIONES)
PAYLOAD = {
    "choices": [{"message": {"role": "assistant", "content": RESPUESTA_IA}}],
    "usage": {"prompt_tokens": 4200, "completion_tokens": 1500},
}


@override_settings(AI_API_KEY="clave-de-prueba", AI_MODEL="modelo-de-prueba")
class MotorIATest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ia@ejemplo.test", email="ia@ejemplo.test", password="Mendoza2026!")
        self.user.profile.nombre = "Mariana"
        self.user.profile.save()
        for clave, pregunta in Q.FLAT.items():
            Answer.objects.create(user=self.user, key=clave, value=f"Texto sobre {pregunta['label']}.")

    def test_genera_informe_con_ia(self):
        with patch("reports.ai._post", return_value=PAYLOAD) as mock:
            informe = engine.generar(self.user)

        self.assertEqual(informe.engine, "ia")
        self.assertEqual(informe.model_name, "modelo-de-prueba")
        self.assertEqual(len(informe.secciones), 9)
        self.assertEqual((informe.tokens_in, informe.tokens_out), (4200, 1500))
        self.assertGreater(float(informe.costo_usd), 0)

        payload = mock.call_args[0][1]
        self.assertEqual(payload["model"], "modelo-de-prueba")
        self.assertIn("Entrevista de intake", payload["messages"][1]["content"])
        # El nombre no viaja al proveedor: sale pseudonimizado y se restaura al volver.
        self.assertNotIn("Mariana", payload["messages"][1]["content"])
        self.assertIn("Mariana", informe.cuerpo)

    def test_el_feedback_entra_en_el_siguiente_informe(self):
        with patch("reports.ai._post", return_value=PAYLOAD) as mock:
            primero = engine.generar(self.user)
            Feedback.objects.create(
                report=primero, resonancia=2,
                desaciertos="Muy genérico", profundizar="El vínculo con mi padre")
            segundo = engine.generar(self.user)
            prompt = mock.call_args_list[-1][0][1]["messages"][1]["content"]

        self.assertEqual(segundo.numero, 2)
        self.assertIn("No le representó: Muy genérico", prompt)
        self.assertIn("Pide profundizar: El vínculo con mi padre", prompt)
        self.assertIn("Informe anterior", prompt)

    def test_sin_clave_cae_al_motor_local(self):
        with override_settings(AI_API_KEY=""):
            informe = engine.generar(self.user)
        self.assertEqual(informe.engine, "local")
        self.assertEqual(len(informe.secciones), 9)

    def test_si_el_proveedor_falla_cae_al_motor_local(self):
        with patch("reports.ai._post", side_effect=ai.AIUnavailable("timeout")):
            informe = engine.generar(self.user)
        self.assertEqual(informe.engine, "local")
        self.assertEqual(Report.objects.filter(user=self.user).count(), 1)

    def test_costo_castiga_hora_pico_y_premia_cache(self):

        valle = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)   # jueves, fuera de pico
        pico = datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc)     # jueves, 02 UTC

        con_cache = engine.calcular_costo(10_000, 2_000, 5_000, cuando=valle)
        sin_cache = engine.calcular_costo(10_000, 2_000, 0, cuando=valle)
        en_pico = engine.calcular_costo(10_000, 2_000, 5_000, cuando=pico)

        self.assertLess(con_cache, sin_cache)
        self.assertAlmostEqual(en_pico, con_cache * 2, delta=0.00002)
        self.assertAlmostEqual(con_cache, 0.001965, delta=0.00002)

    def test_router_usa_premium_solo_cuando_conviene(self):
        ctx = engine.contexto(self.user)
        self.assertEqual(engine.elegir_modelo(self.user, ctx)[0], settings.AI_MODEL)

        perfil = perfil_de(self.user)
        perfil.plan = "pro"
        perfil.pro_until = date.today() + timedelta(days=30)
        perfil.save()

        ctx = engine.contexto(self.user)
        self.assertEqual(engine.elegir_modelo(self.user, ctx)[0], settings.AI_MODEL_PREMIUM)

        primero = Report.objects.create(
            user=self.user, numero=1, titulo="Informe 1", engine="ia", secciones=[],
            model_name=settings.AI_MODEL_PREMIUM)
        Feedback.objects.create(report=primero, resonancia=2)
        ctx = engine.contexto(self.user)
        self.assertEqual(engine.elegir_modelo(self.user, ctx)[0], settings.AI_MODEL_PREMIUM)

        Feedback.objects.all().delete()
        Feedback.objects.create(report=primero, resonancia=5)
        ctx = engine.contexto(self.user)
        self.assertEqual(engine.elegir_modelo(self.user, ctx)[0], settings.AI_MODEL)

    @override_settings(AI_PRESUPUESTO_USD=0.001)
    def test_presupuesto_agotado_no_llama_a_la_api(self):
        Report.objects.create(
            user=self.user, numero=1, titulo="previo", engine="ia",
            model_name="deepseek-flash", costo_usd=0.01, secciones=[])

        permitido, motivo = engine.puede_usar_ia(self.user)
        self.assertFalse(permitido)
        self.assertIn("presupuesto", motivo)

        # Sin presupuesto no se llama a la API y tampoco se inventa un informe local:
        # se levanta SinCreditos para que el pedido vaya a la cola.
        with patch("reports.ai._post", return_value=PAYLOAD) as mock:
            with self.assertRaises(ai.SinCreditos):
                engine.generar(self.user)
        mock.assert_not_called()
        self.assertEqual(Report.objects.count(), 1)

    @override_settings(AI_LIMITE_USUARIO_USD=0.0001)
    def test_limite_por_usuario(self):
        Report.objects.create(
            user=self.user, numero=1, titulo="previo", engine="ia",
            model_name="deepseek-flash", costo_usd=0.01, secciones=[])

        permitido, motivo = engine.puede_usar_ia(self.user)
        self.assertFalse(permitido)
        self.assertIn("usuario", motivo)
        self.assertAlmostEqual(engine.gasto_mes(self.user), 0.01, places=4)
