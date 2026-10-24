"""El texto legal debe decir lo que el sistema hace, en cada etapa del producto."""
from django.test import Client, TestCase, override_settings


class LegalTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_sin_cobros_no_promete_suscripcion(self):
        respuesta = self.client.get("/legal/")
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode()
        self.assertIn("no realiza cobros", html)
        self.assertNotIn("se renuevan automáticamente", html)
        self.assertIn("no hay contrataciones ni cobros habilitados", html)

    @override_settings(PAGOS_ACTIVOS=True)
    def test_con_cobros_describe_renovacion_y_cancelacion(self):
        html = self.client.get("/legal/").content.decode()
        self.assertIn("se renuevan automáticamente", html)
        self.assertIn("cancelar la suscripción en cualquier momento", html)
        self.assertNotIn("no realiza cobros", html)

    def test_declara_el_proveedor_y_la_seudonimizacion(self):
        html = self.client.get("/legal/").content.decode()
        self.assertIn("DeepSeek", html)
        self.assertIn("República Popular China", html)
        self.assertIn("seudonimiza", html)
        # La IP del diagnóstico tiene que estar declarada, no negada en general.
        self.assertIn("Dirección IP en el diagnóstico público", html)

    def test_declara_plazos_que_coinciden_con_el_sistema(self):
        html = self.client.get("/legal/").content.decode()
        for plazo in ("doce meses", "veinticuatro meses", "noventa días", "treinta días"):
            self.assertIn(plazo, html)

    def test_el_ancla_del_arrepentimiento_existe(self):
        html = self.client.get("/legal/").content.decode()
        self.assertIn('id="arrepentimiento"', html)
        self.assertIn('id="supresion"', html)
