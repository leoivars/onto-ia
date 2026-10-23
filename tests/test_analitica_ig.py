"""Control de repetición y lectura de métricas de Instagram."""
from datetime import datetime

from django.test import TestCase
from django.utils import timezone

from web import analitica_ig
from web.models import MetricaPublicacion, Publicacion


class SimilitudTest(TestCase):
    def test_textos_iguales_dan_uno(self):
        self.assertEqual(analitica_ig.similitud("El problema no es lo que le pasa",
                                                "El problema no es lo que le pasa"), 1.0)

    def test_textos_distintos_dan_bajo(self):
        valor = analitica_ig.similitud("El problema no es lo que le pasa",
                                       "Un plan que no se puede verificar es una intención")
        self.assertLess(valor, 0.2)

    def test_parecido_detecta_la_repeticion(self):
        a = Publicacion.objects.create(nombre="a", texto="Lo que evita decir sostiene el problema")
        b = Publicacion.objects.create(nombre="b",
                                       texto="Lo que evita decir es lo que sostiene el problema")
        _, valor = analitica_ig.parecido(b)
        self.assertGreaterEqual(valor, 0.5)
        _, valor_a = analitica_ig.parecido(a)
        self.assertGreaterEqual(valor_a, 0.5)

    def test_descartadas_no_cuentan(self):
        Publicacion.objects.create(nombre="x", texto="Lo que evita decir sostiene el problema",
                                   estado="descartada")
        b = Publicacion.objects.create(nombre="y", texto="Otro texto completamente distinto")
        _, valor = analitica_ig.parecido(b)
        self.assertEqual(valor, 0.0)


class MetricasTest(TestCase):
    def _publicada(self):
        return Publicacion.objects.create(nombre="p", texto="Texto", estado="publicada",
                                          ig_id="123", publicada_en=timezone.now())

    def test_actualizar_guarda_la_foto(self):
        p = self._publicada()
        from unittest.mock import patch

        with patch("web.instagram.insights",
                   return_value={"reach": 1200, "saved": 24, "likes": 90, "shares": 5,
                                 "comments": 3, "impressions": 1800}):
            metrica = analitica_ig.actualizar(p)
        self.assertEqual(metrica.alcance, 1200)
        self.assertEqual(metrica.guardados, 24)
        self.assertEqual(metrica.guardados_por_mil, 20)

    def test_resumen_ordena_por_guardados(self):
        a = Publicacion.objects.create(nombre="a", texto="Uno", estado="publicada", ig_id="1")
        b = Publicacion.objects.create(nombre="b", texto="Dos", estado="publicada", ig_id="2")
        MetricaPublicacion.objects.create(publicacion=a, alcance=1000, guardados=5)
        MetricaPublicacion.objects.create(publicacion=b, alcance=1000, guardados=40)
        datos = analitica_ig.resumen()
        self.assertEqual(datos["filas"][0]["publicacion"], b)
        self.assertIn("guardados por mil", datos["lectura"])

    def test_sin_metricas_lo_dice(self):
        self.assertIn("Todavía no hay métricas", analitica_ig.resumen()["lectura"])


class PanelMetricasTest(TestCase):
    """El panel es solo para staff, así que necesita su propia prueba de humo."""

    def test_panel_responde(self):
        from django.contrib.auth.models import User
        from django.test import Client, override_settings

        staff = User.objects.create_user("jefe", email="jefe@ejemplo.test",
                                         password="clave-larga-123", is_staff=True)
        cliente = Client()
        cliente.force_login(staff)
        sesion = cliente.session
        sesion["otp_ok"] = True
        sesion.save()
        with override_settings(ADMIN_IPS=["127.0.0.1"]):
            respuesta = cliente.get("/metricas/")
        assert respuesta.status_code == 200
        assert "Embudo" in respuesta.content.decode()
