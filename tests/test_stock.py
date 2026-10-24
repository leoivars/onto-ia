"""Cliente de Pixabay: normalización de resultados, elección de clip y descarga."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from web import stock

RESPUESTA_VIDEOS = {
    "total": 2,
    "hits": [
        {
            "id": 111, "tags": "escribir, cuaderno, mano", "duration": 12,
            "pageURL": "https://pixabay.com/videos/id-111/", "user": "ana",
            "videos": {
                "large": {"url": "https://cdn/large.mp4", "width": 1080, "height": 1920, "size": 9000000},
                "medium": {"url": "https://cdn/medium.mp4", "width": 720, "height": 1280, "size": 3000000},
            },
        },
        {
            "id": 222, "tags": "oficina, ventana, luz", "duration": 40,
            "pageURL": "https://pixabay.com/videos/id-222/", "user": "luis",
            "videos": {
                "large": {"url": "https://cdn/l2.mp4", "width": 1080, "height": 1920, "size": 12000000},
            },
        },
    ],
}

RESPUESTA_FOTOS = {
    "hits": [
        {"id": 333, "tags": "ventana, luz", "imageWidth": 1080, "imageHeight": 1920,
         "largeImageURL": "https://cdn/f1.jpg", "pageURL": "https://pixabay.com/photos/333/",
         "user": "eva"},
        {"id": 444, "tags": "paisaje", "imageWidth": 1920, "imageHeight": 1080,
         "largeImageURL": "https://cdn/f2.jpg", "pageURL": "https://pixabay.com/photos/444/",
         "user": "sol"},
    ]
}


@override_settings(PIXABAY_API_KEY="clave-de-prueba", PIXABAY_API="https://pixabay.com/api/")
class StockTest(TestCase):
    @patch("web.stock._get", return_value=RESPUESTA_VIDEOS)
    def test_normaliza_videos_y_pide_verticales(self, get):
        clips = stock.buscar_videos("escribir", limite=2)
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[0]["archivo"], "https://cdn/large.mp4")
        self.assertEqual(clips[0]["alto"], 1920)
        self.assertEqual(clips[0]["tipo"], "video")
        self.assertEqual(clips[0]["autor"], "ana")

        url = get.call_args[0][0]
        self.assertIn("orientation=vertical", url)
        self.assertIn("video_type=film", url)
        self.assertIn("key=clave-de-prueba", url)

    @patch("web.stock._get", return_value=RESPUESTA_FOTOS)
    def test_normaliza_fotos(self, _get):
        fotos = stock.buscar_fotos("ventana", limite=2)
        self.assertEqual(fotos[0]["archivo"], "https://cdn/f1.jpg")
        self.assertEqual(fotos[0]["tipo"], "foto")

    @patch("web.stock._get", return_value=RESPUESTA_VIDEOS)
    def test_elige_el_vertical_mas_grande(self, _get):
        clips = stock.buscar_videos("escribir")
        elegido = stock.elegir(clips)
        self.assertEqual(elegido["id"], 111)

    def test_descarta_apaisados_y_clips_largos(self):
        clips = [
            {"id": 1, "tipo": "video", "ancho": 1920, "alto": 1080, "duracion": 8, "archivo": "x"},
            {"id": 2, "tipo": "video", "ancho": 1080, "alto": 1920, "duracion": 60, "archivo": "y"},
            {"id": 3, "tipo": "video", "ancho": 540, "alto": 960, "duracion": 8, "archivo": "z"},
        ]
        self.assertIsNone(stock.elegir(clips))

    @override_settings(PIXABAY_API_KEY="")
    def test_sin_clave_avisa_claro(self):
        with self.assertRaises(stock.PixabayError) as contexto:
            stock.buscar_videos("lo que sea")
        self.assertIn("PIXABAY_API_KEY", str(contexto.exception))

    @patch("web.stock._get")
    def test_traduce_el_limite_de_consultas(self, get):
        import urllib.error

        get.side_effect = stock.PixabayError("límite de consultas alcanzado (100 por minuto)")
        with self.assertRaises(stock.PixabayError) as contexto:
            stock.buscar_videos("escribir")
        self.assertIn("límite", str(contexto.exception))
