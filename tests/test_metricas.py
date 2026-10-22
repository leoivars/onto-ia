"""Tablero de validación y comando de costos."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from reports.models import Report
from web.metricas import resumen


class MetricasTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="m@ejemplo.test", email="m@ejemplo.test", password="Mendoza2026!")
        self.user.profile.nombre = "Mariana"
        self.user.profile.plan = "pro"
        self.user.profile.save()

    def _informe(self, numero, costo, entrada, salida, cache, motor="ia"):
        return Report.objects.create(
            user=self.user, numero=numero, titulo=f"Informe {numero}", engine=motor,
            model_name="deepseek-flash", secciones=[{"titulo": "Lectura", "cuerpo": "texto"}],
            tokens_in=entrada, tokens_out=salida, tokens_cache=cache, costo_usd=costo)

    def test_resumen_calcula_consumo(self):
        self._informe(1, 0.0020, 5000, 1500, 1000)
        self._informe(2, 0.0015, 4500, 1200, 3000)
        self._informe(3, 0, 0, 0, 0, motor="local")

        m = resumen()
        self.assertEqual(m["informes"], 3)
        self.assertEqual(m["con_ia"], 2)
        self.assertAlmostEqual(m["costo_total"], 0.0035, places=5)
        self.assertAlmostEqual(m["costo_promedio"], 0.00175, places=5)
        self.assertEqual(m["tokens_entrada"], 9500)
        self.assertEqual(m["tokens_cache"], 4000)
        self.assertEqual(m["pct_cache"], 42)
        self.assertEqual(len(m["por_usuario"]), 1)
        self.assertEqual(m["por_usuario"][0]["informes"], 2)

    def test_comando_costos(self):
        self._informe(1, 0.0020, 5000, 1500, 1000)
        salida = StringIO()
        call_command("costos", dias=7, stdout=salida)
        texto = salida.getvalue()
        self.assertIn("m@ejemplo.test", texto)
        self.assertIn("Total del período", texto)

    def test_comando_costos_sin_datos(self):
        salida = StringIO()
        call_command("costos", stdout=salida)
        self.assertIn("Sin informes con IA", salida.getvalue())
