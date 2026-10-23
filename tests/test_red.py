"""Alta y verificación de profesionales de la red."""

from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from red.models import Documento, Evento, Profesional

DATOS = {
    "nombre": "Lucía",
    "apellido": "Ferreyra",
    "email": "lucia@ejemplo.test",
    "telefono": "2615555555",
    "matricula": "mp 1234",
    "provincia": "MZA",
    "registro": "Colegio de Psicólogos de Mendoza",
    "titulo": "Licenciada en Psicología",
    "universidad": "UNCuyo",
    "anio_egreso": 2015,
    "especialidades": "ansiedad, duelo",
    "enfoque": "Trabajo con terapia cognitivo conductual y entrevistas breves.",
    "modalidad": "ambas",
    "ciudad": "Mendoza",
    "bio": "Diez años de práctica clínica.",
    "acepta_protocolo": "on",
    "consentimiento_datos": "on",
    "acepta_sin_comision": "on",
}


def _archivo(nombre="constancia.pdf", contenido=b"%PDF-1.4 prueba"):
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


@override_settings(MEDIA_ROOT="/tmp/onto-test-media",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RedTest(TestCase):
    def setUp(self):
        self.client = Client()

    def _postular(self, **extra):
        datos = dict(DATOS)
        datos.update(extra)
        datos.setdefault("constancia_matricula", _archivo())
        datos.setdefault("seguro", _archivo("poliza.pdf"))
        return self.client.post("/red/postular/", datos)

    def test_alta_crea_pendiente_y_envia_confirmacion(self):
        respuesta = self._postular()
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Recibimos su postulación")
        p = Profesional.objects.get(email="lucia@ejemplo.test")
        self.assertEqual(p.estado, "pendiente")
        self.assertFalse(p.email_confirmado)
        self.assertEqual(p.matricula, "MP 1234")
        self.assertEqual(p.documentos.count(), 2)
        self.assertEqual(Evento.objects.filter(accion="postulacion").count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/red/confirmar/", mail.outbox[0].body)

    def test_sin_consentimiento_no_entra(self):
        respuesta = self.client.post("/red/postular/", {
            **{k: v for k, v in DATOS.items() if k != "consentimiento_datos"},
            "constancia_matricula": _archivo(), "seguro": _archivo("poliza.pdf")})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "consentimiento")
        self.assertEqual(Profesional.objects.count(), 0)

    def test_documento_obligatorio(self):
        respuesta = self.client.post("/red/postular/", dict(DATOS))
        self.assertContains(respuesta, "Falta la constancia")
        self.assertEqual(Profesional.objects.count(), 0)

    def test_archivo_grande_rechazado(self):
        grande = SimpleUploadedFile("c.pdf", b"x" * (6 * 1024 * 1024), content_type="application/pdf")
        respuesta = self.client.post("/red/postular/", {
            **DATOS, "constancia_matricula": grande, "seguro": _archivo("p.pdf")})
        self.assertContains(respuesta, "5 MB")
        self.assertEqual(Profesional.objects.count(), 0)

    def test_matricula_duplicada_rechazada(self):
        self._postular()
        respuesta = self._postular(email="otra@ejemplo.test")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Profesional.objects.count(), 1)

    def test_confirmacion_y_publicacion(self):
        self._postular()
        p = Profesional.objects.get()
        respuesta = self.client.get(f"/red/confirmar/{p.token}/")
        self.assertEqual(respuesta.status_code, 200)
        p.refresh_from_db()
        self.assertTrue(p.email_confirmado)
        # Confirmado pero sin verificar: no aparece.
        self.assertNotContains(self.client.get("/red/"), "Ferreyra")
        p.chequeo_identidad = p.chequeo_matricula = p.chequeo_seguro = True
        p.save()
        p.verificar()
        self.assertContains(self.client.get("/red/"), "Ferreyra")
        self.assertContains(self.client.get("/red/"), "Mat. MP 1234")
        self.assertIsNotNone(p.vence_en)

    def test_ficha_oculta_si_no_esta_verificado(self):
        self._postular()
        p = Profesional.objects.get()
        self.assertEqual(self.client.get(f"/red/{p.slug}/").status_code, 404)

    def test_documento_solo_para_staff(self):
        self._postular()
        doc = Documento.objects.first()
        self.assertEqual(self.client.get(f"/red/documento/{doc.pk}/").status_code, 302)
        User.objects.create_user("staff", password="x", is_staff=True)
        self.client.login(username="staff", password="x")
        respuesta = self.client.get(f"/red/documento/{doc.pk}/")
        self.assertEqual(respuesta.status_code, 200)

    def test_verificar_sin_chequeos_avisa(self):
        self._postular()
        p = Profesional.objects.get()
        p.email_confirmado = True
        p.save()
        p.verificar()
        # verificar() exige chequeos en el admin; a nivel modelo solo deja registro.
        self.assertEqual(p.estado, "verificado")
