"""Busca y baja material de Pixabay para las piezas de Instagram.

Ejemplos:
    manage.py stock buscar "persona escribiendo cuaderno" --tipo video
    manage.py stock buscar "ventana luz mañana" --tipo foto --bajar --nombre fondo-ventana
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from web import stock


class Command(BaseCommand):
    help = "Busca clips o fotos en Pixabay y opcionalmente los descarga al volumen de medios."

    def add_arguments(self, parser):
        parser.add_argument("accion", choices=["buscar"])
        parser.add_argument("consulta", nargs="?", help="Texto a buscar (para buscar).")
        parser.add_argument("--tipo", choices=["video", "foto"], default="video")
        parser.add_argument("--limite", type=int, default=10)
        parser.add_argument("--minutos", type=int, default=0, help="Duración mínima del clip.")
        parser.add_argument("--maximo", type=int, default=30, help="Duración máxima del clip.")
        parser.add_argument("--bajar", action="store_true", help="Descarga el mejor resultado.")
        parser.add_argument("--nombre", default="", help="Nombre del archivo al bajar.")

    def handle(self, *args, **opciones):
        if not stock.configurado():
            raise CommandError("Falta PIXABAY_API_KEY en el .env del servidor. "
                               "No se puede consultar la API sin clave.")

        consulta = (opciones["consulta"] or "").strip()
        if not consulta:
            raise CommandError("Indique qué buscar: manage.py stock buscar \"texto\"")

        if opciones["tipo"] == "video":
            recursos = stock.buscar_videos(
                consulta, limite=opciones["limite"],
                duracion=(opciones["minutos"], opciones["maximo"]))
        else:
            recursos = stock.buscar_fotos(consulta, limite=opciones["limite"])

        if not recursos:
            self.stdout.write(self.style.WARNING("Sin resultados."))
            return

        for r in recursos[:opciones["limite"]]:
            detalle = f"{r['id']} · {r['ancho']}x{r['alto']}"
            if r["tipo"] == "video":
                detalle += f" · {r['duracion']}s · {r['calidad']}"
            self.stdout.write(f"{detalle} · {r['etiquetas'][:70]} · {r['autor']}")

        mejor = stock.elegir(recursos)
        if not mejor:
            self.stdout.write(self.style.WARNING("Ninguno sirve para 1080x1920: probá otra búsqueda."))
            return
        self.stdout.write(self.style.SUCCESS(
            f"Elegido: {mejor['id']} ({mejor['ancho']}x{mejor['alto']})"))

        if opciones["bajar"]:
            nombre = opciones["nombre"] or f"stock-{mejor['id']}"
            extension = "mp4" if mejor["tipo"] == "video" else "jpg"
            destino = Path(settings.MEDIA_ROOT) / "stock" / f"{nombre}.{extension}"
            stock.descargar(mejor, destino)
            self.stdout.write(self.style.SUCCESS(f"Guardado en {destino}"))
            self.stdout.write(stock.credito(mejor))
