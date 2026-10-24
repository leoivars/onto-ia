"""Pseudonimización antes de enviar a un modelo externo, y su registro auditable."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from intake import questions as Q
from intake.models import Answer
from reports import anonimizacion, engine
from reports.models import AuditoriaIA, Report

CLAVE = "Mendoza2026!"

EJEMPLO = (
    "Me llamo Mariana Quiroga y trabajo en la Cooperativa Sancor. Mi correo es "
    "mariana.quiroga@gmail.com y mi teléfono 261 555-4477. Mi DNI es 27.845.112. "
    "En la reunión de junio, mi padre Alberto me dijo que el balance estaba mal. "
    "Alberto repitió eso frente a los socios."
)


class AnonimizacionTest(TestCase):
    def test_reemplaza_datos_identificatorios(self):
        texto, mapa = anonimizacion.anonimizar(
            EJEMPLO, nombre="Mariana Quiroga", ciudad="Mendoza", oficio="contadora")
        for dato in ("Mariana", "Quiroga", "gmail.com", "555-4477", "27.845.112"):
            self.assertNotIn(dato, texto)
        self.assertTrue(mapa)
        self.assertIn("[MAIL", "".join(mapa.keys()) + texto)

    def test_restaura_el_texto_original(self):
        texto, mapa = anonimizacion.anonimizar(EJEMPLO, nombre="Mariana Quiroga")
        vuelta = anonimizacion.restaurar(texto, mapa)
        self.assertIn("Mariana Quiroga", vuelta)
        self.assertIn("mariana.quiroga@gmail.com", vuelta)

    def test_el_mismo_nombre_mantiene_la_misma_marca_entre_campos(self):
        mapa = {}
        uno, mapa = anonimizacion.anonimizar("Mariana llamó.", nombre="Mariana", mapa=mapa)
        dos, mapa = anonimizacion.anonimizar("Mariana insistió.", nombre="Mariana", mapa=mapa)
        marcas = {m for m in mapa if m.startswith("[P")}
        self.assertEqual(len(marcas), 1)
        self.assertIn(list(marcas)[0], uno)
        self.assertIn(list(marcas)[0], dos)

    def test_no_toca_palabras_comunes(self):
        texto, _ = anonimizacion.anonimizar("El lunes de enero fui a Mendoza.")
        self.assertIn("lunes", texto)
        self.assertIn("enero", texto)

    def test_restaurar_tolera_marcas_deformadas(self):
        mapa = {"[P1]": "Mariana"}
        self.assertEqual(anonimizacion.restaurar("Hola [ p 1 ].", mapa), "Hola Mariana.")


@patch("reports.engine.ai.disponible", return_value=True)
class EnvioAnonimizadoTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "anonima", email="anonima@ejemplo.test", password=CLAVE)
        for bloque in Q.BLOCKS:
            for q in bloque["questions"]:
                Answer.objects.update_or_create(
                    user=self.user, key=q["key"],
                    defaults={"value": "Mariana Quiroga contó que su padre Alberto la humilló "
                                       "en la reunión de junio. Escribe a mariana@gmail.com."})
        from web.models import perfil_de

        perfil_de(self.user).__class__.objects.filter(user=self.user).update(nombre="Mariana Quiroga")

    @staticmethod
    def _respuesta():
        cuerpo = "\n\n".join(
            f"## {titulo}\n\nTexto sobre [P1] y su padre, sin datos directos."
            for titulo in ("Lectura del observador", "El quiebre que lo trajo", "Juicios maestros",
                           "Lenguaje, emoción y cuerpo", "Promesas y compromisos",
                           "El costo del patrón"))
        return cuerpo, {"in": 1200, "out": 900, "cache": 0}

    def test_lo_que_sale_no_lleva_el_nombre(self, _disponible):
        capturado = {}

        def falso(ctx, modelo=None):
            capturado["ctx"] = ctx
            return self._respuesta()

        with patch("reports.ai.generar_informe", side_effect=falso):
            informe = engine.generar(self.user)

        enviado = capturado["ctx"]
        self.assertNotIn("Mariana", enviado["entrevista_texto"])
        self.assertNotIn("mariana@gmail.com", enviado["entrevista_texto"])
        self.assertNotIn("Alberto", enviado["entrevista_texto"])
        # Lo que se guarda sí conserva el nombre: la restauración funcionó.
        self.assertIn("Mariana Quiroga", informe.cuerpo)

    def test_queda_el_registro_sin_contenido(self, _disponible):
        with patch("reports.ai.generar_informe", return_value=self._respuesta()):
            engine.generar(self.user)

        registro = AuditoriaIA.objects.get(user=self.user)
        self.assertEqual(len(registro.sha), 32)
        self.assertGreater(registro.sustituciones, 0)
        self.assertGreater(registro.caracteres, 0)
        self.assertEqual(registro.clase, "informe")
        self.assertFalse(hasattr(registro, "texto"))

    def test_el_informe_se_guarda_completo(self, _disponible):
        with patch("reports.ai.generar_informe", return_value=self._respuesta()):
            informe = engine.generar(self.user)
        self.assertIsInstance(informe, Report)
        self.assertNotIn("[P1]", informe.cuerpo)


class RondaAnonimizadaTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "ronda", email="ronda@ejemplo.test", password=CLAVE)
        for bloque in Q.BLOCKS:
            for q in bloque["questions"]:
                Answer.objects.update_or_create(
                    user=self.user, key=q["key"],
                    defaults={"value": "Mariana Quiroga trabaja en Sancor desde 2015."})

    @patch("reports.ai.completar")
    def test_la_ronda_sale_sin_nombres_y_se_restaura(self, completar):
        preguntas = json.dumps([{"key": "sancor-que-dijo", "pregunta": "¿Qué le dijo [P1]?",
                                 "motivo": "Falta el episodio."}])
        capturado = {}

        def falso(sistema, usuario, modelo=None, max_tokens=None):
            capturado["pedido"] = usuario
            return preguntas, {"in": 500, "out": 80, "cache": 0}

        completar.side_effect = falso

        from intake import adaptativa

        entrevista, error = adaptativa.generar(self.user)
        self.assertEqual(error, "")
        self.assertNotIn("Mariana", capturado["pedido"])
        self.assertIn("Mariana Quiroga", entrevista.repreguntas[0]["pregunta"])
        self.assertTrue(AuditoriaIA.objects.filter(user=self.user, clase="ronda").exists())
