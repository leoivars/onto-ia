"""Reels a partir de las piezas: fondo con zoom lento y texto que aparece."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1080, 1920
CREMA = (245, 240, 230)
VERDE = (31, 77, 61)
FUENTES = Path("/usr/share/fonts/truetype/dejavu")


def _f(nombre, tamano):
    return ImageFont.truetype(str(FUENTES / nombre), tamano)


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


def _capa_texto(texto, salida, pie="Coaching ontológico · onto.xz.com.ar"):
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(capa)
    margen = 96

    dibujo.text((margen, 200), "Onto.", font=_f("DejaVuSans-Bold.ttf", 52), fill=CREMA + (255,))
    dibujo.line((margen, 286, ANCHO - margen, 286), fill=CREMA + (90,), width=2)

    tamano = 96
    while tamano > 48:
        fuente = _f("DejaVuSerif-Bold.ttf", tamano)
        lineas = _envolver(dibujo, texto, fuente, ANCHO - 2 * margen)
        if len(lineas) <= 5:
            break
        tamano -= 6

    alto_linea = int(tamano * 1.18)
    total = alto_linea * len(lineas)
    y = (ALTO - total) // 2
    for linea in lineas:
        dibujo.text((margen, y + 4), linea, font=fuente, fill=(0, 0, 0, 90))
        dibujo.text((margen, y), linea, font=fuente, fill=CREMA + (255,))
        y += alto_linea

    dibujo.line((margen, ALTO - 440, ANCHO - margen, ALTO - 440), fill=CREMA + (90,), width=2)
    dibujo.text((margen, ALTO - 400), pie, font=_f("DejaVuSans.ttf", 32), fill=CREMA + (240,))

    capa.save(salida, "PNG")
    return Path(salida)


def _repartir_texto(texto, cantidad):
    """Parte el texto en `cantidad` bloques, respetando el fin de las frases."""
    import re

    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto or "") if f.strip()]
    if len(frases) < cantidad:
        palabras = (texto or "").split()
        if not palabras:
            return [""] * cantidad
        tamano = max(len(palabras) // cantidad, 1)
        frases = [" ".join(palabras[i * tamano:(i + 1) * tamano]) for i in range(cantidad)]
        frases[-1] = " ".join(palabras[(cantidad - 1) * tamano:])
    grupos = [frases[i::cantidad] for i in range(cantidad)]
    return [" ".join(g).strip() for g in grupos]


def _capa_velo(salida):
    """Degradado oscuro hacia abajo: da contraste al texto sin apagar la foto."""
    capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
    pixel = capa.load()
    for y in range(ALTO):
        # Arriba casi transparente; abajo, verde tinta al 72%.
        avance = max((y - ALTO * 0.28) / (ALTO * 0.72), 0)
        alfa = int(min(avance, 1) ** 1.35 * 184)
        for x in range(ANCHO):
            pixel[x, y] = (10, 20, 15, alfa)
    capa.save(salida, "PNG")
    return Path(salida)


def _capas_escalonadas(texto, carpeta, cantidad, pie="Coaching ontológico · onto.xz.com.ar"):
    """Una capa por bloque, cada una en su lugar de la columna: el texto se acumula."""
    grupos = _repartir_texto(texto, cantidad)
    margen = 96
    # La columna vive entre el encabezado y el pie: nunca lo pisa.
    arriba, abajo = 340, ALTO - 560
    tamano = 96
    while tamano > 38:
        fuente = _f("DejaVuSerif-Bold.ttf", tamano)
        borrador = ImageDraw.Draw(Image.new("RGBA", (ANCHO, ALTO)))
        lineas = [_envolver(borrador, g, fuente, ANCHO - 2 * margen) for g in grupos]
        alto_linea = int(tamano * 1.16)
        hueco = int(alto_linea * 0.75)
        total = sum(len(l) * alto_linea for l in lineas) + hueco * (cantidad - 1)
        if all(len(l) <= 4 for l in lineas) and total <= (abajo - arriba):
            break
        tamano -= 6

    alturas = [len(l) * alto_linea for l in lineas]
    total = sum(alturas) + hueco * (cantidad - 1)
    y = arriba + max((abajo - arriba - total) // 2, 0)

    salidas = []
    for indice, grupo_lineas in enumerate(lineas):
        capa = Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))
        dibujo = ImageDraw.Draw(capa)
        dibujo.text((margen, 200), "Onto.", font=_f("DejaVuSans-Bold.ttf", 52), fill=CREMA + (255,))
        dibujo.line((margen, 286, ANCHO - margen, 286), fill=CREMA + (90,), width=2)

        cursor = y
        for linea in grupo_lineas:
            dibujo.text((margen, cursor + 4), linea, font=fuente, fill=(0, 0, 0, 90))
            dibujo.text((margen, cursor), linea, font=fuente, fill=CREMA + (255,))
            cursor += alto_linea

        dibujo.line((margen, ALTO - 440, ANCHO - margen, ALTO - 440), fill=CREMA + (90,), width=2)
        dibujo.text((margen, ALTO - 400), pie, font=_f("DejaVuSans.ttf", 32), fill=CREMA + (240,))

        salida = Path(carpeta) / f"bloque{indice}.png"
        capa.save(salida, "PNG")
        salidas.append(salida)
        y += alturas[indice] + hueco
    return salidas


def _fondo_vertical(foto, salida):
    """Foto teñida, recortada a 1080x1920 y oscurecida para que el texto se lea."""
    from web.tarjetas import _duotono

    imagen = _duotono(foto, (ANCHO, ALTO))
    velo = Image.new("RGBA", (ANCHO, ALTO), (16, 27, 22, 150))
    imagen = Image.alpha_composite(imagen.convert("RGBA"), velo).convert("RGB")
    imagen.save(salida, "JPEG", quality=92)
    return Path(salida)


def reel(texto, salida, fondo=None, segundos=8, fps=30):
    """Genera un MP4 vertical 1080x1920 con zoom lento y texto que aparece."""
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        capa = _capa_texto(texto, f"{tmp}/texto.png")
        if fondo and Path(fondo).exists():
            base = _fondo_vertical(fondo, f"{tmp}/fondo.jpg")
            entrada = ["-loop", "1", "-i", str(base)]
            filtro_fondo = (f"[0:v]scale={ANCHO * 2}:{ALTO * 2},"
                            f"zoompan=z='min(zoom+0.0006,1.10)':d={segundos * fps}"
                            f":s={ANCHO}x{ALTO}:fps={fps},format=yuv420p[bg]")
        else:
            base = Image.new("RGB", (ANCHO, ALTO), VERDE)
            base.save(f"{tmp}/fondo.jpg", "JPEG", quality=90)
            entrada = ["-loop", "1", "-i", f"{tmp}/fondo.jpg"]
            filtro_fondo = f"[0:v]format=yuv420p[bg]"

        filtro = (f"{filtro_fondo};[1:v]format=rgba,fade=in:st=0.5:d=0.9:alpha=1[tx];"
                  f"[bg][tx]overlay=0:0:format=auto[v]")
        orden = [
            "ffmpeg", "-y", *entrada, "-loop", "1", "-i", str(capa),
            "-filter_complex", filtro, "-map", "[v]",
            "-t", str(segundos), "-r", str(fps),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(salida),
        ]
        proceso = subprocess.run(orden, capture_output=True, text=True)
        if proceso.returncode != 0:
            raise RuntimeError(proceso.stderr[-800:])
    return salida


def reel_clip(video, texto, salida, segundos=8, recorte=False, inicio=0, fps=30,
              entradas=None, audio=None):
    """Reel a partir de un clip de stock: recorte 9:16, duotono de marca y texto.

    `recorte=True` toma un clip horizontal y lo recorta al centro; con 4K alcanza
    y sobra resolución. Si el clip es más corto que la pieza, se repite en bucle.
    """
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    video = Path(video)
    if not video.exists():
        raise RuntimeError(f"no existe el clip: {video}")

    # Duotono: negro → verde de marca, blanco → crema. Se aplica sobre escala de grises.
    r = f"31+{245 - 31}*val/255"
    g = f"77+{240 - 77}*val/255"
    b = f"61+{230 - 61}*val/255"

    with tempfile.TemporaryDirectory() as tmp:
        if entradas:
            capas = _capas_escalonadas(texto, tmp, len(entradas))
        else:
            capas = [_capa_texto(texto, f"{tmp}/texto.png")]
            entradas = [0.4]
        if recorte:
            encuadre = ("crop=ih*9/16:ih:(iw-ih*9/16)/2:0,"
                        f"scale={ANCHO}:{ALTO}:flags=lanczos")
        else:
            encuadre = (f"scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase:flags=lanczos,"
                        f"crop={ANCHO}:{ALTO}")

        velo = _capa_velo(f"{tmp}/velo.png")
        partes = [
            f"[0:v]{encuadre},hue=s=0,"
            f"lutrgb=r='{r}':g='{g}':b='{b}',"
            "eq=brightness=-0.10:contrast=1.06,setsar=1,fps={fps}[base]".format(fps=fps)
        ]
        # El velo va antes que los textos: un solo overlay y los bloques encima.
        partes.append("[1:v]format=rgba[velo]")
        partes.append("[base][velo]overlay=0:0[bg]")
        entradas_ffmpeg = ["-loop", "1", "-t", str(segundos), "-i", str(velo)]
        for i, (capa, cuando) in enumerate(zip(capas, entradas)):
            inicio_txt = float(cuando)
            partes.append(f"[{i + 2}:v]format=rgba,"
                          f"fade=in:st={inicio_txt}:d=0.35:alpha=1,"
                          f"fade=out:st={max(float(segundos) - 0.6, 0.3)}:d=0.6:alpha=1[t{i}]")
            previo = "bg" if i == 0 else f"v{i - 1}"
            partes.append(f"[{previo}][t{i}]overlay=0:0:format=auto:enable='gte(t,{inicio_txt})'[v{i}]")
            entradas_ffmpeg += ["-loop", "1", "-t", str(segundos), "-i", str(capa)]

        partes.append(f"[v{len(capas) - 1}]fade=out:st={max(segundos - 0.7, 0)}:d=0.7,"
                      "format=yuv420p[v]")
        filtro = ";".join(partes)

        orden = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-ss", str(inicio), "-t", str(segundos), "-i", str(video),
            *entradas_ffmpeg,
        ]
        if audio and Path(audio).exists():
            orden += ["-i", str(audio)]
        orden += ["-filter_complex", filtro, "-map", "[v]"]
        if audio and Path(audio).exists():
            # Voz normalizada: -16 LUFS es el nivel de podcast, cómodo en el teléfono.
            # Índices: 0 video, 1 velo, 2..N+1 capas de texto → el audio va después.
            orden += ["-map", f"{len(capas) + 2}:a",
                      "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                      "-c:a", "aac", "-b:a", "128k"]
        else:
            orden += ["-an"]
        orden += ["-t", str(segundos), "-r", str(fps),
                  "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                  "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                  str(salida)]
        proceso = subprocess.run(orden, capture_output=True, text=True)
        if proceso.returncode != 0:
            raise RuntimeError(proceso.stderr[-800:])
    return salida
