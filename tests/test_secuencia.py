"""Secuencia de seguimiento: programación, envío, bajas y omisiones."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.core import signing
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from web.correos import programar
from web.models import EmailSecuencia, OptOut

RESPUESTAS = {
    "situacion": "En el trabajo me cambiaron el equipo y no me consultaron nada.",
    "juicio": "Yo soy el que siempre se adapta sin decir nada.",
    "evita": "Pedir una reunión para hablar de cómo quedó mi rol.",
    "silencio": "A mi jefe: que necesito claridad sobre mis tareas.",
    "objetivo": "Salir con un acuerdo escrito sobre el rol.",
}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SecuenciaTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_diagnostico_programa_cuatro_correos(self):
        self.client.post("/diagnostico/", RESPUESTAS)
        self.client.post("/diagnostico/resultado/", {"email": "leo@ejemplo.test"})
        pasos = EmailSecuencia.objects.filter(email="leo@ejemplo.test").order_by("paso")
        self.assertEqual(pasos.count(), 4)
        self.assertEqual([p.paso for p in pasos], [1, 2, 3, 4])
        self.assertFalse(any(p.enviado for p in pasos))
        # Programados en el futuro: el primero, mañana.
        self.assertGreater(pasos[0].programado, timezone.now())

    def test_envia_solo_lo_vencido(self):
        programar("leo@ejemplo.test")
        EmailSecuencia.objects.filter(paso=1).update(programado=timezone.now() - timedelta(hours=1))
        call_command("enviar_secuencia")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("baja-correos", mail.outbox[0].body)
        self.assertEqual(EmailSecuencia.objects.filter(enviado=True).count(), 1)

    def test_baja_del_correo_frena_los_envios(self):
        programar("leo@ejemplo.test")
        EmailSecuencia.objects.update(programado=timezone.now() - timedelta(hours=1))
        token = signing.dumps({"email": "leo@ejemplo.test"}, salt="baja-correos")
        self.client.get(f"/baja-correos/{token}/")
        self.assertTrue(OptOut.objects.filter(email="leo@ejemplo.test").exists())
        call_command("enviar_secuencia")
        self.assertEqual(len(mail.outbox), 0)

    def test_si_se_registro_no_recibe_la_secuencia(self):
        User.objects.create_user("leo", email="leo@ejemplo.test", password="clave-larga-123")
        programar("leo@ejemplo.test")
        EmailSecuencia.objects.update(programado=timezone.now() - timedelta(hours=1))
        call_command("enviar_secuencia")
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(EmailSecuencia.objects.filter(enviado=True).count(), 4)

    def test_programar_dos_veces_no_duplica(self):
        programar("leo@ejemplo.test")
        programar("leo@ejemplo.test")
        self.assertEqual(EmailSecuencia.objects.count(), 4)
