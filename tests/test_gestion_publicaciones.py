"""Panel propio de publicaciones: revisar, aprobar, publicar y descartar sin pasar por /admin/."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from web.models import Publicacion


@override_settings(ADMIN_IPS=["127.0.0.1"])
class GestionPublicacionesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("jefe", email="jefe@ejemplo.test",
                                              password="clave-larga-123", is_staff=True)
        self.publicacion = Publicacion.objects.create(
            nombre="pieza", texto="El problema no es lo que le pasa.", caption="Texto del post.")

    def _entrar(self):
        self.client.force_login(self.staff)
        sesion = self.client.session
        sesion["otp_ok"] = True
        sesion.save()

    def test_solo_staff(self):
        self.assertEqual(self.client.get("/gestion/publicaciones/").status_code, 302)
        self._entrar()
        self.assertEqual(self.client.get("/gestion/publicaciones/").status_code, 200)

    def test_lista_los_borradores(self):
        self._entrar()
        respuesta = self.client.get("/gestion/publicaciones/")
        self.assertContains(respuesta, "El problema no es lo que le pasa")
        self.assertContains(respuesta, "Aprobar mañana 10:00")

    def test_aprobar_programa(self):
        self._entrar()
        self.client.post("/gestion/publicaciones/",
                         {"pk": self.publicacion.pk, "accion": "aprobar", "dias": 2})
        self.publicacion.refresh_from_db()
        self.assertEqual(self.publicacion.estado, "aprobada")
        self.assertEqual(timezone.localtime(self.publicacion.programada).hour, 10)
        self.assertGreater(self.publicacion.programada,
                           timezone.now() + timedelta(days=1))

    def test_descartar(self):
        self._entrar()
        self.client.post("/gestion/publicaciones/",
                         {"pk": self.publicacion.pk, "accion": "descartar"})
        self.publicacion.refresh_from_db()
        self.assertEqual(self.publicacion.estado, "descartada")

    def test_recuperar_descartada(self):
        self.publicacion.estado = "descartada"
        self.publicacion.save()
        self._entrar()
        self.client.post("/gestion/publicaciones/",
                         {"pk": self.publicacion.pk, "accion": "borrador"})
        self.publicacion.refresh_from_db()
        self.assertEqual(self.publicacion.estado, "borrador")

    def test_publicar_usa_la_api(self):
        from unittest.mock import patch

        self._entrar()
        with patch("web.publicaciones.instagram.crear_contenedor", return_value="c1"), \
             patch("web.publicaciones.instagram.esperar_listo", return_value=True), \
             patch("web.publicaciones.instagram.publicar", return_value="m1"), \
             patch("web.publicaciones.instagram.datos_publicacion",
                   return_value={"permalink": "https://instagram.com/p/x"}):
            self.client.post("/gestion/publicaciones/",
                             {"pk": self.publicacion.pk, "accion": "publicar"})
        self.publicacion.refresh_from_db()
        self.assertEqual(self.publicacion.estado, "publicada")
        self.assertEqual(self.publicacion.permalink, "https://instagram.com/p/x")
