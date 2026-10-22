"""Comando de lectura IMAP, probado con un servidor simulado (sin credenciales reales)."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

CABECERA = (b'From: Mariana <mariana@ejemplo.test>\r\n'
            b'Subject: Consulta sobre el informe\r\n'
            b'Date: Wed, 22 Oct 2026 18:00:00 -0300\r\n\r\n')
CUERPO = (b'From: Mariana <mariana@ejemplo.test>\r\n'
          b'To: hola@onto.xz.com.ar\r\n'
          b'Subject: Consulta sobre el informe\r\n'
          b'Date: Wed, 22 Oct 2026 18:00:00 -0300\r\n'
          b'Content-Type: text/plain; charset=utf-8\r\n\r\n'
          b'Hola, quiero saber si el plan incluye dos informes.\r\n')


class FakeIMAP:
    def __init__(self, *a, **k):
        self.guardado = None

    def login(self, usuario, clave):
        return "OK", [b"logged in"]

    def select(self, buzon, readonly=True):
        return "OK", [b"1"]

    def search(self, charset, criterio):
        return "OK", [b"1 2"]

    def fetch(self, uid, partes):
        if "RFC822" in partes:
            return "OK", [(b"1 (RFC822 {100}", CUERPO), b")"]
        return "OK", [(b"1 (BODY[HEADER.FIELDS ...] {100}", CABECERA), b")"]

    def store(self, uid, accion, bandera):
        self.guardado = (uid, accion, bandera)

    def logout(self):
        return "BYE", [b"bye"]


class CorreoTest(SimpleTestCase):
    def test_sin_credenciales_avisa(self):
        with override_settings(), patch.dict("os.environ", {"MAIL_IMAP_USER": "",
                                                           "MAIL_IMAP_PASSWORD": ""}):
            with self.assertRaises(CommandError):
                call_command("correo", "listar", stdout=StringIO())

    @patch("imaplib.IMAP4_SSL", FakeIMAP)
    def test_listar(self):
        salida = StringIO()
        with patch.dict("os.environ", {"MAIL_IMAP_USER": "ontoxz@gmail.com",
                                       "MAIL_IMAP_PASSWORD": "clave-de-prueba"}):
            call_command("correo", "listar", limite=5, stdout=salida)
        texto = salida.getvalue()
        self.assertIn("mariana@ejemplo.test", texto)
        self.assertIn("Consulta sobre el informe", texto)

    @patch("imaplib.IMAP4_SSL", FakeIMAP)
    def test_leer(self):
        salida = StringIO()
        with patch.dict("os.environ", {"MAIL_IMAP_USER": "ontoxz@gmail.com",
                                       "MAIL_IMAP_PASSWORD": "clave-de-prueba"}):
            call_command("correo", "leer", "1", stdout=salida)
        texto = salida.getvalue()
        self.assertIn("De: Mariana", texto)
        self.assertIn("dos informes", texto)
