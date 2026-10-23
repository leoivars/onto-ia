"""Genera las tarjetas que se publican en Instagram, con la identidad de Onto."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1080, 1350
CREMA = (245, 240, 230)
TINTA = (27, 26, 23)
VERDE = (31, 77, 61)
GRIS = (107, 100, 89)

FUENTES = Path("/usr/share/fonts/truetype/dejavu")


def _fuente(nombre, tamano):
    ruta = FUENTES / nombre
    try:
        return ImageFont.truetype(str(ruta), tamano)
    except OSError:
        return ImageFont.load_default()


def _envolver(dibujo, texto, fuente, ancho_max):
    palabras, lineas, actual = texto.split(), [], ""
    for palabra in palabras:
        prueba = f"{actual} {palabra}".strip()
        if dibujo.textlength(prueba, font=fuente) <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def tarjeta(texto, salida, pie="Coaching ontológico con IA · onto.xz.com.ar"):
    """Dibuja una tarjeta 1080x1350 y la guarda como JPEG listo para publicar."""
    imagen = Image.new("RGB", (ANCHO, ALTO), CREMA)
    dibujo = ImageDraw.Draw(imagen)

    margen = 96
    # Marca
    dibujo.text((margen, margen), "Onto.", font=_fuente("DejaVuSans-Bold.ttf", 44), fill=VERDE)
    dibujo.line((margen, margen + 78, ANCHO - margen, margen + 78), fill=(210, 202, 187), width=2)

    # Titular: baja el cuerpo hasta que entre en seis líneas
    tamano = 92
    while tamano > 52:
        fuente = _fuente("DejaVuSerif-Bold.ttf", tamano)
        lineas = _envolver(dibujo, texto, fuente, ANCHO - 2 * margen)
        if len(lineas) <= 6:
            break
        tamano -= 6

    alto_linea = int(tamano * 1.18)
    total = alto_linea * len(lineas)
    y = (ALTO - total) // 2 - 40
    for linea in lineas:
        dibujo.text((margen, y), linea, font=fuente, fill=TINTA)
        y += alto_linea

    # Pie
    dibujo.line((margen, ALTO - 190, ANCHO - margen, ALTO - 190), fill=(210, 202, 187), width=2)
    dibujo.text((margen, ALTO - 152), pie, font=_fuente("DejaVuSans.ttf", 28), fill=GRIS)

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(salida, "JPEG", quality=92, optimize=True)
    return salida
