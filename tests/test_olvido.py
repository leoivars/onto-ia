"""Derecho de supresión: borrado real y verificable de los datos de una persona."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from diagnostico.models import Diagnostico
from red.models import Documento, Profesional
from web.models import Lead


@override_settings(MEDIA_ROOT="/tmp/onto-test-media-olvido",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OlvidoTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.email = "persona@ejemplo.test"
        user = User.objects.create_user("persona", email=self.email, password="clave-larga-123")
        from web.models import perfil_de
        perfil_de(user).nombre = "Persona"
        Diagnostico.objects.create(email=self.email, nombre="Persona", respuestas={"a": "b"},
                                   teaser="t", informe="i", motor="local")
        Lead.objects.create(email=self.email)

    def _token(self):
        self.client.post("/baja/", {"email": self.email})
        cuerpo = mail.outbox[-1].body
        return cuerpo.split("/baja/")[1].split("/")[0]

    def test_pedido_envia_enlace_y_no_borra_todavia(self):
        respuesta = self.client.post("/baja/", {"email": self.email})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/baja/", mail.outbox[0].body)
        self.assertEqual(Diagnostico.objects.count(), 1)

    def test_enlace_borra_todo(self):
        token = self._token()
        respuesta = self.client.get(f"/baja/{token}/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Datos eliminados")
        self.assertEqual(Diagnostico.objects.filter(email=self.email).count(), 0)
        self.assertEqual(Lead.objects.filter(email=self.email).count(), 0)
        self.assertEqual(User.objects.filter(email=self.email).count(), 0)

    def test_token_invalido_no_borra(self):
        respuesta = self.client.get("/baja/token-falso/")
        self.assertEqual(respuesta.status_code, 410)
        self.assertEqual(Diagnostico.objects.count(), 1)

    def test_borra_tambien_legajo_y_documentos(self):
        profesional = Profesional.objects.create(
            nombre="Ana", apellido="Paz", email=self.email, matricula="MP 777", provincia="MZA",
            registro="Colegio", titulo="Psicóloga", especialidades="ansiedad",
            enfoque="Texto")
        doc = Documento.objects.create(
            profesional=profesional, tipo="matricula",
            archivo=SimpleUploadedFile("c.pdf", b"%PDF-1.4 x"))
        ruta = doc.archivo.path

        token = self._token()
        self.client.get(f"/baja/{token}/")

        self.assertEqual(Profesional.objects.filter(email=self.email).count(), 0)
        self.assertEqual(Documento.objects.count(), 0)
        import os
        self.assertFalse(os.path.exists(ruta))

    def test_borrar_cuenta_desde_el_panel_tambien_limpia_diagnosticos(self):
        User.objects.filter(email=self.email).update(password="pbkdf2_sha256$600000$x$y")
        self.client.force_login(User.objects.get(email=self.email))
        self.client.post("/cuenta/eliminar/")
        self.assertEqual(Diagnostico.objects.filter(email=self.email).count(), 0)
        self.assertEqual(Lead.objects.filter(email=self.email).count(), 0)

    def test_purga_por_retencion(self):
        viejo = Diagnostico.objects.create(email="viejo@ejemplo.test", respuestas={}, teaser="",
                                           informe="", motor="local")
        Diagnostico.objects.filter(pk=viejo.pk).update(
            created_at=timezone.now() - timedelta(days=800))
        call_command("purgar_datos", "--dry-run")
        self.assertEqual(Diagnostico.objects.filter(pk=viejo.pk).count(), 1)
        call_command("purgar_datos")
        self.assertEqual(Diagnostico.objects.filter(pk=viejo.pk).count(), 0)
        self.assertEqual(Diagnostico.objects.count(), 1)

    def test_purga_visitas_de_mas_de_90_dias(self):
        from web.models import Visita
        vieja = Visita.objects.create(ruta="/", origen="instagram", sesion="x" * 32)
        Visita.objects.filter(pk=vieja.pk).update(creada=timezone.now() - timedelta(days=120))
        call_command("purgar_datos")
        self.assertFalse(Visita.objects.filter(pk=vieja.pk).exists())
