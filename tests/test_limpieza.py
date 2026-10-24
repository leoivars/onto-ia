"""Limpieza de medios: clips y reels vencidos, sin tocar lo que todavía se usa."""
import tempfile
from datetime import timedelta
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from web.models import Publicacion


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class LimpiezaTest(TestCase):
    def setUp(self):
        from django.conf import settings

        self.media = Path(settings.MEDIA_ROOT)
        (self.media / "stock").mkdir(parents=True, exist_ok=True)
        (self.media / "publicaciones").mkdir(parents=True, exist_ok=True)

    def _pieza(self, nombre, dias, clip=True, video=True, estado="publicada"):
        p = Publicacion.objects.create(nombre=nombre, texto="Texto", formato="reel", estado=estado)
        if clip:
            ruta = self.media / "stock" / f"{nombre}.mp4"
            ruta.write_bytes(b"\x00" * 40_000)
            p.clip_archivo = f"stock/{nombre}.mp4"
        if video:
            ruta = self.media / "publicaciones" / f"{nombre}.mp4"
            ruta.write_bytes(b"\x00" * 60_000)
            p.video = f"publicaciones/{nombre}.mp4"
        p.publicada_en = timezone.now() - timedelta(days=dias)
        p.save()
        return p

    def test_borra_lo_vencido_y_conserva_lo_reciente(self):
        viejo = self._pieza("viejo", dias=120)
        nuevo = self._pieza("nuevo", dias=5)

        call_command("limpiar_media", dias_clip=30, dias_render=90)

        viejo.refresh_from_db()
        self.assertEqual(viejo.clip_archivo, "")
        self.assertFalse((self.media / "publicaciones" / "viejo.mp4").exists())
        self.assertTrue((self.media / "publicaciones" / "nuevo.mp4").exists())
        self.assertTrue((self.media / "stock" / "nuevo.mp4").exists())

    def test_no_toca_los_borradores(self):
        borrador = self._pieza("borrador", dias=200, estado="borrador")
        call_command("limpiar_media", dias_clip=1, dias_render=1)
        self.assertTrue((self.media / "stock" / "borrador.mp4").exists())
        self.assertTrue((self.media / "publicaciones" / "borrador.mp4").exists())

    def test_simular_no_borra_nada(self):
        self._pieza("viejo", dias=120)
        call_command("limpiar_media", dias_clip=1, dias_render=1, simular=True)
        self.assertTrue((self.media / "stock" / "viejo.mp4").exists())
