"""Pseudonimización antes de enviar texto a un modelo externo.

Qué hace: reemplaza nombres propios, correos, teléfonos y documentos por marcas
estables ([P1], [C1], [MAIL]...), llama al modelo con el texto marcado y
restaura los valores en la respuesta. El texto original nunca sale del servidor.

Qué no hace: no convierte el texto en anónimo. Una escena con edad, ciudad y
oficio puede reidentificarse. Es pseudonimización, y así se declara.

Lo que queda registrado: el hash del texto enviado, la cantidad de sustituciones
y el modelo usado. Nunca el contenido.
"""

import hashlib
import re

from django.utils import timezone

CORREO = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
TELEFONO = re.compile(r"(?<!\d)(?:\+?54[\s-]?)?(?:\d{2,4}[\s-]?){2,4}\d{2,4}(?!\d)")
DOCUMENTO = re.compile(r"\b\d{2}[.\-]?\d{3}[.\-]?\d{3}\b|\b\d{2}-\d{8}-\d\b")
URL = re.compile(r"https?://\S+")

# Palabras que se escriben en mayúscula sin ser nombres propios.
COMUNES = {
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "setiembre", "octubre", "noviembre", "diciembre", "lunes",
    "martes", "miércoles", "jueves", "viernes", "sábado", "domingo", "dios",
    "argentina", "mendoza", "buenos", "aires", "cordoba", "córdoba", "rosario",
    "profundo", "estudio", "gratis", "onto", "usted", "señor", "señora", "don",
    "doña", "licenciado", "licenciada", "doctor", "doctora", "abogado", "abogada",
    "universidad", "colegio", "escuela", "hospital", "clínica", "clinica", "banco",
}

MARCA = "[{tipo}]"
NOMBRE = re.compile(r"[«\"“']([^»\"”']{2,60})[»\"”']")


def _limpio(texto):
    return " ".join((texto or "").split())


def _agregar(mapa, valor, tipo):
    """Devuelve la marca para un valor y la registra una sola vez."""
    valor = _limpio(valor)
    if len(valor) < 3:
        return ""
    for marca, original in mapa.items():
        if original.lower() == valor.lower():
            return marca
    indice = sum(1 for m in mapa if m.startswith(f"[{tipo}")) + 1
    marca = f"[{tipo}{indice}]"
    mapa[marca] = valor
    return marca


def _reemplazar_conocidos(texto, mapa, valores, tipo):
    for valor in valores:
        valor = _limpio(valor)
        if len(valor) < 3:
            continue
        marca = _agregar(mapa, valor, tipo)
        if marca:
            texto = re.sub(re.escape(valor), marca, texto, flags=re.IGNORECASE)
    return texto


def _parece_nombre(valor):
    """Solo se toca lo que parece un nombre propio: una a tres palabras capitalizadas."""
    palabras = valor.split()
    if not 1 <= len(palabras) <= 3:
        return False
    if any(not p[:1].isupper() for p in palabras):
        return False
    if any(p.lower() in COMUNES for p in palabras):
        return False
    return all(p.replace("-", "").isalpha() for p in palabras)


def _nombres_propios(texto, mapa):
    """Nombres probables: mayúscula en medio de la oración, repetidos o en comillas."""
    for coincidencia in NOMBRE.finditer(texto):
        valor = coincidencia.group(1).strip()
        if not _parece_nombre(valor):
            continue
        marca = _agregar(mapa, valor, "P")
        if marca:
            texto = texto.replace(coincidencia.group(0), marca)

    candidatos = {}
    for coincidencia in re.finditer(r"(?<=[a-záéíóúñ,;:]\s)([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})", texto):
        palabra = coincidencia.group(1)
        if palabra.lower() in COMUNES:
            continue
        candidatos[palabra] = candidatos.get(palabra, 0) + 1
    for palabra, veces in candidatos.items():
        if veces < 2:
            continue
        marca = _agregar(mapa, palabra, "P")
        if marca:
            texto = re.sub(rf"\b{re.escape(palabra)}\b", marca, texto)
    return texto


def anonimizar(texto, nombre="", ciudad="", oficio="", otros=None, mapa=None):
    """Devuelve (texto marcado, mapa). El mapa es lo único que permite restaurar.

    Si se pasa un mapa existente, se reutiliza: así dos campos del mismo envío
    comparten marcas y [P1] significa la misma persona en todo el prompt.
    """
    mapa = {} if mapa is None else mapa
    texto = texto or ""

    texto = CORREO.sub(lambda m: _agregar(mapa, m.group(0), "MAIL") or m.group(0), texto)
    texto = URL.sub(lambda m: _agregar(mapa, m.group(0), "URL") or m.group(0), texto)
    texto = DOCUMENTO.sub("[DOC]", texto)
    texto = TELEFONO.sub(lambda m: "[TEL]" if len(re.sub(r"\D", "", m.group(0))) >= 8 else m.group(0), texto)

    valores = [nombre] + [p for p in (nombre.split() if nombre else []) if len(p) > 2]
    texto = _reemplazar_conocidos(texto, mapa, valores, "P")
    texto = _reemplazar_conocidos(texto, mapa, [ciudad], "C")
    texto = _reemplazar_conocidos(texto, mapa, [oficio], "O")
    texto = _reemplazar_conocidos(texto, mapa, otros or [], "P")
    texto = _nombres_propios(texto, mapa)

    return texto, mapa


def restaurar(texto, mapa):
    """Devuelve el texto con los valores originales. Tolera marcas deformadas."""
    if not mapa:
        return texto or ""
    for marca, original in sorted(mapa.items(), key=lambda x: -len(x[0])):
        tipo = marca.strip("[]").rstrip("0123456789")
        sufijo = marca.strip("[]")[len(tipo):]
        if not sufijo:
            texto = texto.replace(marca, original)
            continue
        patron = re.compile(rf"\[\s*{tipo}\s*_?\s*{sufijo}\s*\]", re.IGNORECASE)
        texto = patron.sub(original, texto)
    return texto


def huella(texto):
    return hashlib.sha256((texto or "").encode("utf-8")).hexdigest()[:32]


def registrar(user, modelo, texto_enviado, mapa, uso, costo, clase="informe"):
    """Deja constancia de qué salió: hash, sustituciones y modelo. Nunca el contenido."""
    from .models import AuditoriaIA

    return AuditoriaIA.objects.create(
        user=user,
        modelo=modelo or "",
        clase=clase,
        sha=huella(texto_enviado),
        caracteres=len(texto_enviado or ""),
        sustituciones=len(mapa or {}),
        tokens_in=int(uso.get("in", 0)),
        tokens_out=int(uso.get("out", 0)),
        costo=costo or 0,
        cuando=timezone.now(),
    )
