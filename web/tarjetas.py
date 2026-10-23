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
    except OSError as exc:
        raise RuntimeError(
            f"Falta la tipografía {ruta}. Instalá fonts-dejavu-core en la imagen: "
            f"sin eso la tarjeta sale con una fuente de reemplazo ilegible.") from exc


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


def _duotono(ruta_foto, tamano=(ANCHO, ALTO)):
    """Lleva la foto a la paleta del sitio: verde tinta en las sombras, crema en las luces."""
    from PIL import ImageOps

    foto = Image.open(ruta_foto).convert("L")
    foto = ImageOps.fit(foto, tamano, method=Image.LANCZOS)
    foto = ImageOps.autocontrast(foto, cutoff=1)
    return ImageOps.colorize(foto, black=(26, 44, 35), white=CREMA).convert("RGB")


def tarjeta_foto(texto, salida, fondo, pie="Coaching ontológico con IA · onto.xz.com.ar"):
    """Tarjeta con foto de fondo, teñida al tono del sitio y con el texto en crema."""
    from PIL import ImageFilter

    imagen = _duotono(fondo)
    # Desenfoque suave: quita textura detrás de la tipografía sin perder la foto.
    imagen = imagen.filter(ImageFilter.GaussianBlur(7))
    dibujo = ImageDraw.Draw(imagen, "RGBA")

    # Velo inferior: asegura contraste sin apagar toda la foto.
    alto_velo = int(ALTO * 0.62)
    for i in range(alto_velo):
        alfa = int(238 * (i / alto_velo) ** 1.15)
        dibujo.line((0, ALTO - alto_velo + i, ANCHO, ALTO - alto_velo + i),
                    fill=(16, 27, 22, alfa))

    # Velo superior corto: sostiene la marca sobre zonas claras.
    for i in range(240):
        alfa = int(150 * (1 - i / 240) ** 1.3)
        dibujo.line((0, i, ANCHO, i), fill=(16, 27, 22, alfa))

    margen = 96
    dibujo.text((margen, margen + 3), "Onto.", font=_fuente("DejaVuSans-Bold.ttf", 44),
                fill=(0, 0, 0, 100))
    dibujo.text((margen, margen), "Onto.", font=_fuente("DejaVuSans-Bold.ttf", 44), fill=CREMA)
    dibujo.line((margen, margen + 78, ANCHO - margen, margen + 78), fill=(CREMA[0], CREMA[1],
                                                                         CREMA[2], 90), width=2)

    tamano = 84
    while tamano > 46:
        fuente = _fuente("DejaVuSerif-Bold.ttf", tamano)
        lineas = _envolver(dibujo, texto, fuente, ANCHO - 2 * margen)
        if len(lineas) <= 5:
            break
        tamano -= 6

    alto_linea = int(tamano * 1.16)
    y = ALTO - 210 - alto_linea * len(lineas)
    for linea in lineas:
        dibujo.text((margen, y + 3), linea, font=fuente, fill=(0, 0, 0, 110))
        dibujo.text((margen, y), linea, font=fuente, fill=CREMA)
        y += alto_linea

    dibujo.line((margen, ALTO - 150, ANCHO - margen, ALTO - 150),
                fill=(CREMA[0], CREMA[1], CREMA[2], 90), width=2)
    dibujo.text((margen, ALTO - 118), pie, font=_fuente("DejaVuSans.ttf", 29),
                fill=(CREMA[0], CREMA[1], CREMA[2], 235))

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(salida, "JPEG", quality=90, optimize=True)
    return salida


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
