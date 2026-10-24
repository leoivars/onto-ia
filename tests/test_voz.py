"""Voz: proveedores, caché y acople con el render del reel."""
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from web import voz
from web.models import Publicacion

SIN_FFMPEG = shutil.which("ffmpeg") is None


class ProveedorTest(TestCase):
    @override_settings(AZURE_SPEECH_KEY="", ELEVENLABS_API_KEY="")
    def test_sin_claves_no_hay_proveedor(self):
        self.assertFalse(voz.disponible())
        with self.assertRaises(voz.VozError) as contexto:
            voz.generar("hola", "/tmp/x.mp3")
        self.assertIn("proveedor", str(contexto.exception))

    @override_settings(AZURE_SPEECH_KEY="k", AZURE_SPEECH_REGION="sa-saopaulo-1",
                       ELEVENLABS_API_KEY="")
    def test_azure_tiene_prioridad(self):
        self.assertEqual(voz.proveedor(), "azure")

    @override_settings(AZURE_SPEECH_KEY="", ELEVENLABS_API_KEY="k", ELEVENLABS_VOICE_ID="v1")
    def test_elevenlabs_cuando_no_hay_azure(self):
        self.assertEqual(voz.proveedor(), "elevenlabs")


@override_settings(AZURE_SPEECH_KEY="clave", AZURE_SPEECH_REGION="sa-saopaulo-1")
class GeneracionTest(TestCase):
    def test_escribe_el_audio_y_no_repite_la_llamada(self):
        destino = Path(tempfile.mkdtemp()) / "voz.mp3"
        with patch("web.voz._post_azure", return_value=b"ID3" + b"\x00" * 5000) as llamada:
            voz.generar("Una promesa tiene dos partes y una fecha.", destino)
            self.assertTrue(destino.exists())
            self.assertEqual(llamada.call_count, 1)

            voz.generar("Una promesa tiene dos partes y una fecha.", destino)
            self.assertEqual(llamada.call_count, 1)  # vino de caché en disco

            voz.generar("Otro texto distinto.", destino)
            self.assertEqual(llamada.call_count, 2)

    def test_rechaza_audio_demasiado_corto(self):
        with patch("web.voz._post_azure", return_value=b"x" * 100):
            with self.assertRaises(voz.VozError):
                voz.generar("texto", Path(tempfile.mkdtemp()) / "c.mp3")


class RepartoTest(TestCase):
    def test_reparte_los_bloques_dentro_de_la_duracion(self):
        marcas = voz.repartir(9.0, 3)
        self.assertEqual(len(marcas), 3)
        self.assertLess(marcas[0], marcas[1])
        self.assertLess(marcas[2], 9.0)
        self.assertGreaterEqual(marcas[0], 0.3)

    def test_sin_bloques_no_devuelve_nada(self):
        self.assertEqual(voz.repartir(9.0, 0), [])


class RenderConVozTest(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_el_reel_lleva_pista_de_audio(self):
        if SIN_FFMPEG:
            self.skipTest("ffmpeg no está instalado")
        from django.conf import settings

        media = Path(settings.MEDIA_ROOT)
        (media / "stock").mkdir(parents=True, exist_ok=True)
        (media / "voz").mkdir(parents=True, exist_ok=True)
        clip = media / "stock" / "base.mp4"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                        "testsrc=size=1080x1920:rate=30:duration=3", "-pix_fmt", "yuv420p",
                        str(clip)], capture_output=True, check=True)
        audio = media / "voz" / "con-voz.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=4",
                        str(audio)], capture_output=True, check=True)

        from web import publicaciones as cola

        publicacion = Publicacion.objects.create(
            nombre="con-voz", texto="Una frase. Otra frase. Y una tercera.", formato="reel",
            clip_archivo="stock/base.mp4", clip_modo="vertical",
            guion="Una frase. Otra frase. Y una tercera.")

        with patch("web.voz.disponible", return_value=True), \
             patch("web.voz.generar", return_value=audio):
            salida = cola.render(publicacion)

        self.assertTrue(salida.exists())
        datos = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "stream=codec_type", "-of", "csv=p=0", str(salida)],
                               capture_output=True, text=True).stdout
        self.assertIn("audio", datos)
        self.assertIn("video", datos)
        publicacion.refresh_from_db()
        self.assertTrue(publicacion.tiempos)
