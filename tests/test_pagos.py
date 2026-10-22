"""Suscripciones con Mercado Pago: creación, webhook firmado y activación del plan."""
import hashlib
import hmac
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from pagos.models import Pago, Suscripcion
from web.models import perfil_de

EMAIL = "pagos@ejemplo.test"
CLAVE = "Mendoza2026!"


def firma(secreto, data_id, request_id, ts="1700000000"):
    manifiesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secreto.encode(), manifiesto.encode(), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


@override_settings(MP_ACCESS_TOKEN="TEST-token", MP_WEBHOOK_SECRET="secreto-de-prueba",
                   PAGOS_ACTIVOS=True)
class PagosTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username=EMAIL, email=EMAIL, password=CLAVE)
        self.client = Client()
        self.client.force_login(self.user)

    @patch("pagos.views.mp.crear_preapproval", return_value=("2c9abc", "https://mp/checkout/123"))
    def test_suscribirse_crea_suscripcion_pendiente(self, mock):
        respuesta = self.client.get("/pagos/suscribirse/pro/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], "https://mp/checkout/123")
        sus = Suscripcion.objects.get(user=self.user)
        self.assertEqual(sus.estado, "pending")
        self.assertEqual(sus.plan, "pro")
        self.assertEqual(str(sus.monto), "6900.00")

    def test_plan_invalido_redirige(self):
        respuesta = self.client.get("/pagos/suscribirse/gratis/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Suscripcion.objects.exists())

    @override_settings(PAGOS_ACTIVOS=False)
    def test_en_beta_no_se_puede_pagar(self):
        respuesta = self.client.get("/pagos/suscribirse/pro/", follow=True)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(Suscripcion.objects.exists())
        self.assertContains(respuesta, "beta")

    def test_webhook_sin_firma_es_rechazado(self):
        respuesta = self.client.post("/pagos/webhook/?type=subscription_preapproval&data.id=abc")
        self.assertEqual(respuesta.status_code, 401)

    def test_webhook_firma_incorrecta_es_rechazada(self):
        respuesta = self.client.post(
            "/pagos/webhook/?type=subscription_preapproval&data.id=abc",
            HTTP_X_SIGNATURE="ts=1700000000,v1=deadbeef",
            HTTP_X_REQUEST_ID="req-1")
        self.assertEqual(respuesta.status_code, 401)

    @patch("pagos.views.mp.obtener_preapproval")
    def test_webhook_autoriza_y_activa_plan(self, obtener):
        sus = Suscripcion.objects.create(
            user=self.user, plan="pro", preapproval_id="2c9abc", monto=6900, estado="pending")
        obtener.return_value = {
            "id": "2c9abc", "status": "authorized",
            "auto_recurring": {"transaction_amount": 6900, "currency_id": "ARS"},
            "next_payment_date": (date.today() + timedelta(days=31)).isoformat() + "T00:00:00.000-03:00",
        }
        respuesta = self.client.post(
            "/pagos/webhook/?type=subscription_preapproval&data.id=2c9abc",
            HTTP_X_SIGNATURE=firma("secreto-de-prueba", "2c9abc", "req-1"),
            HTTP_X_REQUEST_ID="req-1")
        self.assertEqual(respuesta.status_code, 200)

        sus.refresh_from_db()
        self.assertEqual(sus.estado, "authorized")
        self.assertIsNotNone(sus.proximo_pago)

        perfil = perfil_de(self.user)
        self.assertEqual(perfil.plan, "pro")
        self.assertGreaterEqual(perfil.pro_until, date.today() + timedelta(days=30))

    @patch("pagos.views.mp.obtener_preapproval")
    def test_webhook_repetido_no_extiende_dos_veces(self, obtener):
        Suscripcion.objects.create(
            user=self.user, plan="pro", preapproval_id="2c9abc", monto=6900, estado="pending")
        obtener.return_value = {"id": "2c9abc", "status": "authorized",
                                "auto_recurring": {"transaction_amount": 6900}}
        for _ in range(2):
            self.client.post(
                "/pagos/webhook/?type=subscription_preapproval&data.id=2c9abc",
                HTTP_X_SIGNATURE=firma("secreto-de-prueba", "2c9abc", "req-1"),
                HTTP_X_REQUEST_ID="req-1")
        perfil = perfil_de(self.user)
        self.assertLessEqual(perfil.pro_until, date.today() + timedelta(days=32))

    @patch("pagos.views.mp.cancelar_preapproval", return_value={})
    def test_cancelar_mantiene_acceso(self, _mock):
        sus = Suscripcion.objects.create(
            user=self.user, plan="pro", preapproval_id="2c9abc", monto=6900, estado="authorized")
        perfil = perfil_de(self.user)
        perfil.plan = "pro"
        perfil.pro_until = date.today() + timedelta(days=20)
        perfil.save()

        respuesta = self.client.post(f"/pagos/cancelar/{sus.pk}/", follow=True)
        self.assertEqual(respuesta.status_code, 200)
        sus.refresh_from_db()
        self.assertEqual(sus.estado, "cancelled")
        perfil.refresh_from_db()
        self.assertEqual(perfil.plan, "pro")
        self.assertEqual(perfil.pro_until, date.today() + timedelta(days=20))

    @patch("pagos.views.mp.obtener_pago")
    def test_webhook_de_pago_registra(self, obtener):
        obtener.return_value = {
            "id": 998877, "status": "approved", "transaction_amount": 6900,
            "currency_id": "ARS", "external_reference": str(self.user.pk),
        }
        respuesta = self.client.post(
            "/pagos/webhook/?type=payment&data.id=998877",
            HTTP_X_SIGNATURE=firma("secreto-de-prueba", "998877", "req-9"),
            HTTP_X_REQUEST_ID="req-9")
        self.assertEqual(respuesta.status_code, 200)
        pago = Pago.objects.get(mp_payment_id="998877")
        self.assertEqual(pago.estado, "approved")
        self.assertEqual(pago.user, self.user)
