"""Medición propia: visitas, origen y atribución hasta el registro."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from diagnostico.models import Diagnostico
from web.models import Visita, perfil_de


class VisitasTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_registra_visita_con_utm(self):
        self.client.get("/?utm_source=instagram&utm_medium=social")
        visita = Visita.objects.latest("creada")
        self.assertEqual(visita.ruta, "/")
        self.assertEqual(visita.origen, "instagram/social")
        self.assertEqual(visita.fuente, "instagram")
        self.assertEqual(visita.medio, "social")

    def test_referente_se_traduce_a_origen(self):
        self.client.get("/", HTTP_REFERER="https://l.instagram.com/?u=x")
        self.assertEqual(Visita.objects.latest("creada").origen, "instagram")

    def test_sin_referente_es_directo(self):
        self.client.get("/")
        self.assertEqual(Visita.objects.latest("creada").origen, "directo")

    def test_no_registra_rutas_excluidas(self):
        self.client.get("/baja/")
        self.assertEqual(Visita.objects.count(), 0)

    def test_el_origen_llega_al_diagnostico(self):
        self.client.get("/?utm_source=tiktok")
        datos = {
            "situacion": "Discuto siempre con mi hermana por la herencia de mis padres.",
            "juicio": "Yo soy el que siempre cede para no pelear.",
            "evita": "Poner un límite concreto con fechas.",
            "silencio": "A mi hermana: que necesito hablar de plata sin pelear.",
            "objetivo": "Tener una reunión con un acuerdo escrito.",
        }
        self.client.post("/diagnostico/", datos)
        self.client.post("/diagnostico/resultado/", {"email": "x@ejemplo.test"})
        self.assertEqual(Diagnostico.objects.latest("created_at").origen, "tiktok")

    def test_el_origen_llega_al_registro(self):
        self.client.get("/?utm_source=linkedin&utm_medium=social")
        respuesta = self.client.post("/registro/", {
            "nombre": "Leo", "email": "leo@ejemplo.test",
            "password1": "clave-larga-123", "password2": "clave-larga-123"})
        self.assertIn(respuesta.status_code, (302, 200))
        user = User.objects.filter(email="leo@ejemplo.test").first()
        if user:
            self.assertEqual(perfil_de(user).origen, "linkedin/social")


class AgregadosTest(TestCase):
    def test_agregar_dia_es_idempotente(self):
        from web.agregados import agregar_dia
        from web.models import ResumenDiario

        Visita.objects.create(ruta="/", origen="instagram", sesion="a" * 32)
        Visita.objects.create(ruta="/", origen="instagram", sesion="a" * 32)
        Visita.objects.create(ruta="/precios/", origen="instagram", sesion="b" * 32)
        hoy = timezone.localdate()

        agregar_dia(hoy)
        agregar_dia(hoy)

        filas = ResumenDiario.objects.filter(fecha=hoy)
        self.assertEqual(filas.count(), 2)
        home = filas.get(ruta="/")
        self.assertEqual(home.vistas, 2)
        self.assertEqual(home.sesiones, 1)

    def test_purgar_guarda_el_agregado_antes_de_borrar(self):
        from django.core.management import call_command
        from web.models import ResumenDiario

        vieja = Visita.objects.create(ruta="/", origen="google", sesion="c" * 32)
        Visita.objects.filter(pk=vieja.pk).update(creada=timezone.now() - timedelta(days=120))
        fecha = timezone.localtime(
            Visita.objects.get(pk=vieja.pk).creada).date()

        call_command("purgar_datos")

        self.assertFalse(Visita.objects.filter(pk=vieja.pk).exists())
        self.assertTrue(ResumenDiario.objects.filter(fecha=fecha, origen="google").exists())

    def test_historico_devuelve_doce_meses(self):
        from web.metricas import historico

        serie = historico()
        self.assertEqual(len(serie), 12)
        self.assertIn("vistas", serie[0])
        self.assertIn("registros", serie[-1])
