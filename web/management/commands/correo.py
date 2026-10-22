"""Lectura de la casilla de contacto por IMAP.

Uso:
    python manage.py correo listar --limite 10
    python manage.py correo listar --no-leidos
    python manage.py correo leer 1234

Credenciales por entorno (nunca en el código):
    MAIL_IMAP_HOST (por defecto imap.gmail.com)
    MAIL_IMAP_PORT (por defecto 993)
    MAIL_IMAP_USER
    MAIL_IMAP_PASSWORD   contraseña de aplicación de Google
"""
import email
import imaplib
import os
import re
from email.header import decode_header, make_header

from django.core.management.base import BaseCommand, CommandError


def _texto(valor):
    if not valor:
        return ""
    try:
        return str(make_header(decode_header(valor)))
    except Exception:
        return str(valor)


def _cuerpo(mensaje, limite=2500):
    if mensaje.is_multipart():
        for parte in mensaje.walk():
            if parte.get_content_type() == "text/plain" and "attachment" not in str(
                    parte.get("Content-Disposition") or ""):
                carga = parte.get_payload(decode=True) or b""
                return carga.decode(parte.get_content_charset() or "utf-8", "replace")[:limite]
        for parte in mensaje.walk():
            if parte.get_content_type() == "text/html":
                carga = parte.get_payload(decode=True) or b""
                html = carga.decode(parte.get_content_charset() or "utf-8", "replace")
                limpio = re.sub(r"<[^>]+>", " ", html)
                return re.sub(r"\s+", " ", limpio)[:limite]
        return ""
    carga = mensaje.get_payload(decode=True) or b""
    return carga.decode(mensaje.get_content_charset() or "utf-8", "replace")[:limite]


class Command(BaseCommand):
    help = "Lista o lee mensajes de la casilla de contacto por IMAP."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["listar", "leer"])
        parser.add_argument("uid", nargs="?", type=str)
        parser.add_argument("--limite", type=int, default=10)
        parser.add_argument("--no-leidos", action="store_true")
        parser.add_argument("--marcar-leido", action="store_true")

    def handle(self, *args, **opciones):
        usuario = os.environ.get("MAIL_IMAP_USER", "")
        clave = os.environ.get("MAIL_IMAP_PASSWORD", "")
        if not usuario or not clave:
            raise CommandError(
                "Faltan MAIL_IMAP_USER y MAIL_IMAP_PASSWORD. Genere una contraseña de "
                "aplicación en la cuenta de Google y cárguela en .env.")

        anfitrion = os.environ.get("MAIL_IMAP_HOST", "imap.gmail.com")
        puerto = int(os.environ.get("MAIL_IMAP_PORT", "993"))

        try:
            imap = imaplib.IMAP4_SSL(anfitrion, puerto)
            imap.login(usuario, clave)
        except imaplib.IMAP4.error as exc:
            raise CommandError(f"No se pudo iniciar sesión IMAP: {exc}") from exc

        imap.select("INBOX", readonly=not opciones["marcar_leido"])

        if opciones["accion"] == "listar":
            criterio = "UNSEEN" if opciones["no_leidos"] else "ALL"
            estado, datos = imap.search(None, criterio)
            uids = (datos[0] or b"").split()
            if not uids:
                self.stdout.write("Sin mensajes.")
                return
            for uid in uids[-opciones["limite"]:][::-1]:
                estado, crudo = imap.fetch(uid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                cabecera = next((p[1] for p in crudo if isinstance(p, tuple)), b"")
                mensaje = email.message_from_bytes(cabecera)
                self.stdout.write(
                    f"[{uid.decode()}] {_texto(mensaje.get('Date'))[:31]} | "
                    f"{_texto(mensaje.get('From'))[:48]} | {_texto(mensaje.get('Subject'))[:70]}")
            return

        if not opciones["uid"]:
            raise CommandError("Indique el UID: manage.py correo leer <uid>")
        estado, crudo = imap.fetch(opciones["uid"].encode(), "(RFC822)")
        if estado != "OK":
            raise CommandError("No se encontró ese mensaje.")
        mensaje = email.message_from_bytes(next(p[1] for p in crudo if isinstance(p, tuple)))
        self.stdout.write(f"De: {_texto(mensaje.get('From'))}")
        self.stdout.write(f"Para: {_texto(mensaje.get('To'))}")
        self.stdout.write(f"Fecha: {_texto(mensaje.get('Date'))}")
        self.stdout.write(f"Asunto: {_texto(mensaje.get('Subject'))}")
        self.stdout.write("")
        self.stdout.write(_cuerpo(mensaje))

        if opciones["marcar_leido"]:
            imap.store(opciones["uid"].encode(), "+FLAGS", "\\Seen")
            self.stdout.write("\n[guardado como leído]")

        imap.logout()
