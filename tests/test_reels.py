"""Reels: clip de stock, render con ffmpeg, ruta pública y publicación."""
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from web import publicaciones as cola
from web import stock
from web.models import Publicacion

CLIP = {"id": 368623, "tipo": "video", "etiquetas": "writing notebook", "duracion": 6,
        "ancho": 1080, "alto": 1920, "archivo": "https://cdn/clip.mp4", "calidad": "large",
        "bytes": 2400000, "autor": "gulshari_jamil", "pagina": "", "modo": "vertical"}

SIN_FFMPEG = shutil.which("ffmpeg") is None


def clip_falso(destino):
    """Genera un clip vertical de dos segundos para probar el render sin red."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i",
                    "testsrc=size=1080x1920:rate=30:duration=2", "-pix_fmt", "yuv420p",
                    str(destino)], capture_output=True, check=True)
    return destino


class ConsultaTest(TestCase):
    def test_cada_tema_tiene_su_busqueda_en_ingles(self):
        self.assertEqual(cola.consulta_para("El reproche habla del otro"), "writing notebook hand")
        self.assertIn("calendar", cola.consulta_para("Una promesa incumplida"))
        self.assertIn("office", cola.consulta_para("Su jefe y las reuniones"))

    def test_sin_tema_conocido_usa_la_base(self):
        self.assertEqual(cola.consulta_para("Cualquier otra cosa"), cola.CONSULTA_BASE)


@override_settings(PIXABAY_API_KEY="clave-de-prueba")
class ClipTest(TestCase):
    @patch("web.stock.descargar")
    @patch("web.stock.buscar_videos", return_value=[CLIP])
    def test_el_borrador_se_queda_con_su_clip(self, buscar, descargar):
        publicacion = Publicacion.objects.create(
            nombre="promesa-reel", texto="Una promesa tiene dos partes y una fecha.",
            formato="reel")
        self.assertTrue(cola.agregar_clip(publicacion))
        publicacion.refresh_from_db()
        self.assertEqual(publicacion.clip_id, "368623")
        self.assertEqual(publicacion.clip_modo, "vertical")
        self.assertEqual(publicacion.clip_archivo, "stock/promesa-reel.mp4")
        self.assertTrue(publicacion.consulta)

    @override_settings(PIXABAY_API_KEY="")
    def test_sin_clave_el_borrador_sigue_siendo_valido(self):
        publicacion = Publicacion.objects.create(
            nombre="sin-clave", texto="Texto", formato="reel")
        self.assertFalse(cola.agregar_clip(publicacion))
        self.assertEqual(publicacion.clip_archivo, "")


@override_settings(PIXABAY_API_KEY="clave-de-prueba")
class RenderTest(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_render_produce_un_mp4_vertical(self):
        if SIN_FFMPEG:
            self.skipTest("ffmpeg no está instalado")
        media = Path(settings.MEDIA_ROOT)
        clip_falso(media / "stock" / "prueba.mp4")
        publicacion = Publicacion.objects.create(
            nombre="prueba-reel", texto="El pedido habla de usted.", formato="reel",
            clip_archivo="stock/prueba.mp4", clip_modo="vertical")
        salida = cola.render(publicacion, segundos=3)
        self.assertTrue(salida.exists())
        self.assertGreater(salida.stat().st_size, 20_000)
        publicacion.refresh_from_db()
        self.assertEqual(publicacion.video, "publicaciones/prueba-reel.mp4")

        datos = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "stream=width,height,codec_name", "-of", "csv=p=0", str(salida)],
                               capture_output=True, text=True).stdout
        self.assertIn("1080,1920", datos)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class RutaVideoTest(TestCase):
    def test_sirve_el_mp4_con_su_tipo(self):
        media = Path(settings.MEDIA_ROOT)
        (media / "publicaciones").mkdir(parents=True, exist_ok=True)
        (media / "publicaciones" / "pieza.mp4").write_bytes(b"\x00" * 20_000)
        respuesta = self.client.get("/ig/pieza.mp4")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "video/mp4")
        self.assertIn("max-age=300", respuesta["Cache-Control"])

    def test_rechaza_nombres_invalidos(self):
        self.assertEqual(self.client.get("/ig/../secreto.mp4").status_code, 404)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_publicar_reel_usa_el_contenedor_de_video(self):
        media = Path(settings.MEDIA_ROOT)
        (media / "publicaciones").mkdir(parents=True, exist_ok=True)
        (media / "publicaciones" / "pieza.mp4").write_bytes(b"\x00" * 20_000)
        publicacion = Publicacion.objects.create(
            nombre="pieza", texto="Texto", caption="Pie", formato="reel", estado="aprobada",
            video="publicaciones/pieza.mp4")
        with patch("web.instagram.crear_contenedor_reel", return_value="c1") as crear, \
             patch("web.instagram.esperar_listo") as esperar, \
             patch("web.instagram.publicar", return_value="m1"), \
             patch("web.instagram.datos_publicacion", return_value={"permalink": "https://ig/p/x"}):
            cola.publicar(publicacion)
        self.assertIn(".mp4?v=", crear.call_args[0][0])
        self.assertGreaterEqual(esperar.call_args.kwargs.get("intentos", 20), 60)
        publicacion.refresh_from_db()
        self.assertEqual(publicacion.estado, "publicada")


@override_settings(PIXABAY_API_KEY="clave-de-prueba")
class RitmoTest(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_el_texto_entra_en_los_tiempos_medidos(self):
        if SIN_FFMPEG:
            self.skipTest("ffmpeg no está instalado")
        media = Path(settings.MEDIA_ROOT)
        clip_falso(media / "stock" / "ritmo.mp4")
        publicacion = Publicacion.objects.create(
            nombre="reel-ritmo", texto="Primera frase. Segunda frase. Tercera frase.",
            formato="reel", clip_archivo="stock/ritmo.mp4", clip_modo="vertical",
            tiempos=[0.0, 1.0, 2.0], bpm=120)
        salida = cola.render(publicacion, segundos=4)
        self.assertTrue(salida.exists())
        self.assertGreater(salida.stat().st_size, 20_000)

    def test_los_bloques_respetan_las_frases(self):
        from web.video import _repartir_texto

        bloques = _repartir_texto("Una. Dos. Tres.", 3)
        self.assertEqual(len(bloques), 3)
        self.assertEqual(bloques[1], "Dos.")
