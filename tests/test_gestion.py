"""Panel único de administración: todo en una página."""
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from web.models import Publicacion


@override_settings(ADMIN_IPS=["127.0.0.1"])
class GestionTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("jefe", email="jefe@ejemplo.test",
                                              password="clave-larga-123", is_staff=True)
        Publicacion.objects.create(nombre="uno", texto="Texto de prueba", estado="borrador")
        Publicacion.objects.create(nombre="dos", texto="Otra pieza", estado="publicada",
                                   ig_id="1", permalink="https://instagram.com/p/x")

    def _entrar(self):
        self.client.force_login(self.staff)
        sesion = self.client.session
        sesion["otp_ok"] = True
        sesion.save()

    def test_requiere_staff(self):
        self.assertEqual(self.client.get("/gestion/").status_code, 302)

    def test_muestra_los_bloques(self):
        self._entrar()
        respuesta = self.client.get("/gestion/")
        self.assertEqual(respuesta.status_code, 200)
        for texto in ("Instagram", "Historias", "Sistema", "Publicaciones", "Informes en cola"):
            self.assertContains(respuesta, texto)

    def test_cuenta_los_borradores(self):
        self._entrar()
        respuesta = self.client.get("/gestion/")
        self.assertEqual(respuesta.context["conteos"]["borrador"], 1)
        self.assertEqual(respuesta.context["conteos"]["publicada"], 1)

    def test_publicar_historia_invalida_no_llama_a_la_api(self):
        from unittest.mock import patch

        self._entrar()
        with patch("web.instagram.crear_contenedor") as crear:
            self.client.post("/gestion/", {"accion": "historia", "archivo": "../etc/passwd"})
            crear.assert_not_called()

    def test_lista_las_historias_disponibles(self):
        import os
        from django.conf import settings as cfg

        carpeta = os.path.join(cfg.MEDIA_ROOT, "publicaciones")
        os.makedirs(carpeta, exist_ok=True)
        with open(os.path.join(carpeta, "historia-prueba.jpg"), "wb") as f:
            f.write(b"x" * 1200)

        self._entrar()
        respuesta = self.client.get("/gestion/")
        nombres = [h["nombre"] for h in respuesta.context["historias"]]
        self.assertIn("historia-prueba", nombres)
