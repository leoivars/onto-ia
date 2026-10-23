"""Cola de publicaciones: nada sale sin aprobación."""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from web.models import Publicacion
from web.publicaciones import generar, programar, publicar, publicar_vencidas


@override_settings(MEDIA_ROOT="/tmp/onto-test-publicaciones")
class PublicacionesTest(TestCase):
    def _borrador(self, nombre="prueba"):
        return generar(nombre, "El problema no es lo que le pasa.", "Texto de prueba.")

    def test_generar_deja_borrador_y_crea_la_imagen(self):
        publicacion, creada = self._borrador()
        self.assertTrue(creada)
        self.assertEqual(publicacion.estado, "borrador")
        from pathlib import Path
        self.assertTrue((Path("/tmp/onto-test-publicaciones/publicaciones/prueba.jpg")).exists())

    def test_generar_dos_veces_no_duplica(self):
        self._borrador()
        self._borrador()
        self.assertEqual(Publicacion.objects.count(), 1)

    def test_programar_deja_fecha_a_las_diez(self):
        publicacion, _ = self._borrador()
        programar(publicacion, dias=1)
        publicacion.refresh_from_db()
        self.assertEqual(publicacion.estado, "aprobada")
        self.assertEqual(timezone.localtime(publicacion.programada).hour, 10)
        self.assertGreater(publicacion.programada, timezone.now())

    def test_no_publica_borradores(self):
        self._borrador()
        with patch("web.publicaciones.instagram.crear_contenedor") as crear:
            publicar_vencidas()
            crear.assert_not_called()

    def test_publica_lo_aprobado_y_vencido(self):
        publicacion, _ = self._borrador()
        publicacion.estado = "aprobada"
        publicacion.programada = timezone.now() - timedelta(minutes=5)
        publicacion.save()

        with patch("web.publicaciones.instagram.crear_contenedor", return_value="c1"), \
             patch("web.publicaciones.instagram.esperar_listo", return_value=True), \
             patch("web.publicaciones.instagram.publicar", return_value="m1"), \
             patch("web.publicaciones.instagram.datos_publicacion",
                   return_value={"permalink": "https://instagram.com/p/x"}):
            publicadas = publicar_vencidas()

        publicacion.refresh_from_db()
        self.assertEqual(publicadas, 1)
        self.assertEqual(publicacion.estado, "publicada")
        self.assertEqual(publicacion.ig_id, "m1")
        self.assertEqual(publicacion.permalink, "https://instagram.com/p/x")

    def test_error_de_la_api_queda_registrado(self):
        from web.instagram import InstagramError

        publicacion, _ = self._borrador()
        with patch("web.publicaciones.instagram.crear_contenedor",
                   side_effect=InstagramError("400: imagen inválida")):
            publicar(publicacion)
        publicacion.refresh_from_db()
        self.assertEqual(publicacion.estado, "error")
        self.assertIn("imagen inválida", publicacion.error)
