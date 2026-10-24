"""Voz para los reels: texto a audio con el proveedor configurado.

Dos proveedores, misma interfaz. Se usa el que tenga clave en el .env del servidor:

- Azure Speech  → AZURE_SPEECH_KEY + AZURE_SPEECH_REGION (500.000 caracteres gratis por mes).
- ElevenLabs    → ELEVENLABS_API_KEY + ELEVENLABS_VOICE_ID (plan pago = licencia comercial).

El audio se guarda en caché por huella del texto y de la voz: el mismo guion no se
paga dos veces, y regenerar un reel no vuelve a llamar a la API.

Regla de la casa: nada de voces clonadas de personas reales sin permiso, y si el
plan es gratuito, el audio no se publica.
"""

import hashlib
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings


class VozError(Exception):
    pass


def proveedor():
    """Cuál está configurado, sin llamar a nadie."""
    if getattr(settings, "AZURE_SPEECH_KEY", ""):
        return "azure"
    if getattr(settings, "ELEVENLABS_API_KEY", ""):
        return "elevenlabs"
    return ""


def disponible():
    return bool(proveedor())


def huella(texto, voz=""):
    base = f"{proveedor()}|{voz or _voz_por_defecto()}|{' '.join((texto or '').split())}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def _voz_por_defecto():
    if proveedor() == "azure":
        return getattr(settings, "AZURE_VOZ", "es-AR-TomasNeural")
    return getattr(settings, "ELEVENLABS_VOICE_ID", "")


def _post_azure(texto, voz):
    region = getattr(settings, "AZURE_SPEECH_REGION", "")
    if not region:
        raise VozError("falta AZURE_SPEECH_REGION")

    # SSML: sin esto Azure no pronuncia bien las pausas de puntuación larga.
    ssml = (
        f'<speak version="1.0" xml:lang="es-AR"><voice name="{voz}">'
        f'<prosody rate="-4%">{_escapar(texto)}</prosody>'
        "</voice></speak>"
    )
    pedido = urllib.request.Request(
        f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
        data=ssml.encode("utf-8"), method="POST")
    pedido.add_header("Ocp-Apim-Subscription-Key", settings.AZURE_SPEECH_KEY)
    pedido.add_header("Content-Type", "application/ssml+xml")
    pedido.add_header("X-Microsoft-OutputFormat", "audio-24khz-48kbitrate-mono-mp3")
    pedido.add_header("User-Agent", "Onto/1.0")
    return _bajar_audio(pedido)


def _post_elevenlabs(texto, voz):
    if not voz:
        raise VozError("falta ELEVENLABS_VOICE_ID")
    cuerpo = json.dumps({
        "text": texto,
        "model_id": getattr(settings, "ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0},
    }).encode("utf-8")
    pedido = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz}?output_format=mp3_44100_128",
        data=cuerpo, method="POST")
    pedido.add_header("xi-api-key", settings.ELEVENLABS_API_KEY)
    pedido.add_header("Content-Type", "application/json")
    pedido.add_header("User-Agent", "Onto/1.0")
    return _bajar_audio(pedido)


def _bajar_audio(pedido, timeout=120):
    try:
        with urllib.request.urlopen(pedido, timeout=timeout) as respuesta:
            datos = respuesta.read()
    except urllib.error.HTTPError as exc:
        detalle = ""
        try:
            detalle = exc.read().decode("utf-8", "ignore")[:200]
        except Exception:
            pass
        raise VozError(f"el proveedor rechazó la llamada ({exc.code}): {detalle}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise VozError(f"no se pudo contactar al proveedor: {exc}") from exc
    return datos


def _escapar(texto):
    return (texto or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generar(texto, salida, voz=None, forzar=False):
    """Genera el audio del guion. Devuelve la ruta y reutiliza caché si ya existe."""
    if not disponible():
        raise VozError("no hay proveedor de voz configurado (Azure o ElevenLabs)")
    texto = (texto or "").strip()
    if not texto:
        raise VozError("el guion está vacío")
    if len(texto) > 4000:
        raise VozError("el guion supera los 4000 caracteres: conviene partirlo")

    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    voz = voz or _voz_por_defecto()

    # La caché se valida por huella del texto: si cambió el guion, el audio viejo no sirve.
    marca = salida.with_suffix(salida.suffix + ".huella")
    actual = huella(texto, voz)
    if salida.exists() and marca.exists() and not forzar:
        if marca.read_text(encoding="utf-8").strip() == actual:
            return salida

    datos = _post_azure(texto, voz) if proveedor() == "azure" else _post_elevenlabs(texto, voz)
    # Se valida acá y no en el transporte: un proveedor puede devolver 200 con poco cuerpo.
    if len(datos) < 2000:
        raise VozError("el audio devuelto es demasiado corto: revisá la clave o la voz")
    salida.write_bytes(datos)
    marca.write_text(actual, encoding="utf-8")
    return salida


def duracion(archivo):
    """Duración en segundos del audio o video, con ffprobe."""
    try:
        salida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(archivo)],
            capture_output=True, text=True, check=True).stdout.strip()
        return float(salida or 0)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError) as exc:
        raise VozError(f"no se pudo medir la duración: {exc}") from exc


def repartir(duracion_total, cantidad, inicio=0.35, cola=0.5):
    """Momentos de entrada de cada bloque de texto, proporcionales a la voz.

    Sin timestamps por palabra del proveedor, el reparto por cantidad de caracteres
    es lo más estable: cada bloque entra cuando la voz ya dijo la parte anterior.
    """
    if cantidad <= 0:
        return []
    util = max(duracion_total - inicio - cola, 0.6)
    paso = util / cantidad
    return [round(inicio + i * paso, 2) for i in range(cantidad)]
