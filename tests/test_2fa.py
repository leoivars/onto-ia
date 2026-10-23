"""Segundo factor obligatorio para administradores."""
import pyotp
from django.contrib.auth.models import User
from django.test import Client, TestCase

from web.models import DispositivoTOTP


class DosFactoresTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user("admin", email="admin@ejemplo.test",
                                              password="clave-larga-123", is_staff=True)
        self.cliente = User.objects.create_user("cliente", email="c@ejemplo.test",
                                                password="clave-larga-123")

    def _entrar(self, usuario=None):
        self.client.force_login(usuario or self.staff)

    def test_admin_sin_segundo_factor_no_entra_al_panel(self):
        self._entrar()
        respuesta = self.client.get("/admin/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/seguridad/2fa/", respuesta["Location"])

    def test_cliente_normal_no_se_ve_afectado(self):
        self._entrar(self.cliente)
        self.assertEqual(self.client.get("/panel/").status_code, 200)

    def test_configuracion_exige_codigo_valido(self):
        self._entrar()
        self.assertEqual(self.client.get("/seguridad/2fa/").status_code, 200)
        dispositivo = DispositivoTOTP.objects.get(user=self.staff)
        self.assertFalse(dispositivo.confirmado_en)

        malo = self.client.post("/seguridad/2fa/", {"codigo": "000000"})
        self.assertContains(malo, "no coincide")
        dispositivo.refresh_from_db()
        self.assertFalse(dispositivo.confirmado_en)

        bueno = self.client.post(
            "/seguridad/2fa/", {"codigo": pyotp.TOTP(dispositivo.secreto).now()})
        self.assertContains(bueno, "Guarde estos códigos")
        dispositivo.refresh_from_db()
        self.assertTrue(dispositivo.confirmado_en)
        self.assertEqual(len(dispositivo.codigos_respaldo), 8)

    def test_con_codigo_entra_al_panel(self):
        self._entrar()
        self.client.get("/seguridad/2fa/")
        dispositivo = DispositivoTOTP.objects.get(user=self.staff)
        self.client.post("/seguridad/2fa/", {"codigo": pyotp.TOTP(dispositivo.secreto).now()})
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_verificacion_al_volver_a_entrar(self):
        dispositivo = DispositivoTOTP.objects.create(
            user=self.staff, secreto=pyotp.random_base32())
        from django.utils import timezone
        dispositivo.confirmado_en = timezone.now()
        dispositivo.save()

        self._entrar()
        respuesta = self.client.get("/admin/")
        self.assertIn("/seguridad/verificar/", respuesta["Location"])

        self.assertContains(self.client.post("/seguridad/verificar/", {"codigo": "123456"}),
                            "incorrecto")
        respuesta = self.client.post("/seguridad/verificar/",
                                     {"codigo": pyotp.TOTP(dispositivo.secreto).now()})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_codigo_de_respaldo_sirve_una_sola_vez(self):
        from web import seguridad
        from django.utils import timezone

        dispositivo = DispositivoTOTP.objects.create(
            user=self.staff, secreto=pyotp.random_base32(), confirmado_en=timezone.now())
        claros, hashes = seguridad.generar_respaldo()
        dispositivo.codigos_respaldo = hashes
        dispositivo.save()

        self._entrar()
        respuesta = self.client.post("/seguridad/verificar/", {"codigo": claros[0]})
        self.assertEqual(respuesta.status_code, 302)

        # El mismo código ya no sirve
        self.client.logout()
        self._entrar()
        self.assertContains(self.client.post("/seguridad/verificar/", {"codigo": claros[0]}),
                            "incorrecto")


class DosFactoresOpcionalTest(TestCase):
    """Un cliente puede activarlo si quiere, y desactivarlo cuando quiera."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("cliente2", email="cli2@ejemplo.test",
                                             password="clave-larga-123")

    def test_cliente_sin_segundo_factor_entra_normal(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/panel/").status_code, 200)
        self.assertEqual(self.client.get("/cuenta/").status_code, 200)

    def test_cliente_puede_activarlo(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/seguridad/2fa/").status_code, 200)
        dispositivo = DispositivoTOTP.objects.get(user=self.user)
        respuesta = self.client.post("/seguridad/2fa/",
                                     {"codigo": pyotp.TOTP(dispositivo.secreto).now()})
        self.assertContains(respuesta, "Guarde estos códigos")
        self.assertTrue(self.client.get("/panel/").status_code, 200)

    def test_con_segundo_factor_activo_se_le_pide_el_codigo(self):
        from django.utils import timezone

        DispositivoTOTP.objects.create(user=self.user, secreto=pyotp.random_base32(),
                                       confirmado_en=timezone.now())
        self.client.force_login(self.user)
        respuesta = self.client.get("/panel/")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/seguridad/verificar/", respuesta["Location"])

    def test_cliente_puede_desactivarlo(self):
        from django.utils import timezone

        DispositivoTOTP.objects.create(user=self.user, secreto=pyotp.random_base32(),
                                       confirmado_en=timezone.now())
        self.client.force_login(self.user)
        self.client.post("/seguridad/desactivar/")
        self.assertFalse(DispositivoTOTP.objects.filter(user=self.user).exists())
        self.assertEqual(self.client.get("/panel/").status_code, 200)

    def test_admin_no_puede_desactivarlo(self):
        from django.utils import timezone

        staff = User.objects.create_user("admin2", email="a2@ejemplo.test",
                                         password="clave-larga-123", is_staff=True)
        DispositivoTOTP.objects.create(user=staff, secreto=pyotp.random_base32(),
                                       confirmado_en=timezone.now())
        self.client.force_login(staff)
        self.client.post("/seguridad/desactivar/")
        self.assertTrue(DispositivoTOTP.objects.filter(user=staff).exists())
