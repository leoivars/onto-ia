"""Cola de informes cuando el motor de IA se queda sin créditos."""
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase, override_settings

from intake import questions as Q
from intake.models import Answer
from reports import ai, cola
from reports.models import InformeEnCola, Report
from web.models import perfil_de

DATOS = {
    "situacion": "Discuto siempre con mi socio por cómo repartimos el trabajo.",
    "juicio": "Yo soy el que siempre cede para no pelear.",
    "evita": "Poner una fecha concreta para hablar de la sociedad.",
    "silencio": "A mi socio: que estoy cansado de sostener todo.",
    "objetivo": "Tener una reunión con un acuerdo escrito.",
}


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ColaTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("leo", email="leo@ejemplo.test",
                                             password="clave-larga-123")
        perfil_de(self.user).nombre = "Leo"
        self.user.profile.save()

    def test_encolar_avisa_una_vez(self):
        cola.encolar(self.user, "402 insufficient balance")
        self.assertEqual(InformeEnCola.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("quedó en cola", mail.outbox[0].body)

        cola.encolar(self.user, "otra vez")
        self.assertEqual(InformeEnCola.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_procesar_genera_y_avisa(self):
        cola.encolar(self.user, "sin saldo")
        mail.outbox.clear()
        informe = Report.objects.create(user=self.user, numero=1, titulo="Informe",
                                        engine="ia", secciones=[], cuerpo="")
        with patch("reports.cola.engine.generar", return_value=informe):
            generados, restantes, motivo = cola.procesar()

        self.assertEqual((generados, restantes), (1, 0))
        fila = InformeEnCola.objects.get()
        self.assertEqual(fila.estado, "listo")
        self.assertEqual(fila.report, informe)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/informes/", mail.outbox[0].body)

    def test_si_sigue_sin_creditos_no_quema_la_cola(self):
        cola.encolar(self.user, "sin saldo")
        with patch("reports.cola.engine.generar", side_effect=ai.SinCreditos("402 no balance")):
            generados, restantes, motivo = cola.procesar()

        self.assertEqual(generados, 0)
        self.assertEqual(restantes, 1)
        self.assertIn("sin créditos", motivo)
        fila = InformeEnCola.objects.get()
        self.assertEqual(fila.estado, "pendiente")
        self.assertEqual(fila.intentos, 1)
        self.assertIn("402", fila.ultimo_error)

    def test_no_reemplaza_el_informe_por_plantilla(self):
        cola.encolar(self.user, "sin saldo")
        with patch("reports.cola.engine.generar", side_effect=ai.SinCreditos("402")):
            cola.procesar()
        self.assertEqual(Report.objects.count(), 0)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class VistaColaTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("leo2", email="leo2@ejemplo.test",
                                             password="clave-larga-123")
        perfil = perfil_de(self.user)
        perfil.nombre = "Leo"
        perfil.plan = "pro"
        from datetime import date, timedelta
        perfil.pro_until = date.today() + timedelta(days=30)
        perfil.save()
        for clave in list(Q.FLAT)[:25]:
            Answer.objects.create(user=self.user, key=clave, value="Respuesta de prueba larga.")
        self.client.force_login(self.user)

    def test_sin_creditos_el_pedido_va_a_la_cola(self):
        with patch("reports.views.engine.generar", side_effect=ai.SinCreditos("402 no balance")):
            respuesta = self.client.post("/informes/generar/", follow=True)
        self.assertContains(respuesta, "quedó en cola")
        self.assertEqual(InformeEnCola.objects.count(), 1)
        self.assertEqual(Report.objects.count(), 0)

    def test_si_insiste_se_le_dice_que_ya_esta_en_cola(self):
        InformeEnCola.objects.create(user=self.user, motivo="sin saldo")
        with patch("reports.views.engine.generar") as generar:
            respuesta = self.client.post("/informes/generar/", follow=True)
        self.assertContains(respuesta, "ya está en cola")
        generar.assert_not_called()
        self.assertEqual(InformeEnCola.objects.count(), 1)
