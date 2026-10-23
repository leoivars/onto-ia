"""Líneas de ayuda y detección de señales de riesgo.

Fuente única de verdad: si cambia un número, se cambia acá y en ningún otro lado.

Verificado el 23/10/2026:
- 148 opción 0: salud mental de Mendoza, gratuita, 24 horas (mendoza.gov.ar).
- 0800 345 1435: Centro de Asistencia al Suicida, todo el país, 8 a 24.
- 135: mismo centro, gratuito desde CABA y GBA.
- 911: emergencias en todo el país.
- 144: violencia de género, 24 horas.
- 102: niñez y adolescencia, 24 horas.
"""

import unicodedata

LINEAS = [
    {
        "nombre": "Emergencias",
        "numero": "911",
        "detalle": "Si hay peligro inmediato para usted o para otra persona, las 24 horas.",
    },
    {
        "nombre": "Salud Mental Mendoza",
        "numero": "148, opción 0",
        "detalle": "Gratuita, las 24 horas. Profesionales de la Dirección de Salud Mental.",
    },
    {
        "nombre": "Centro de Asistencia al Suicida",
        "numero": "0800 345 1435",
        "detalle": "Desde todo el país, de 8 a 24. En CABA y GBA también el 135.",
    },
    {
        "nombre": "Violencia de género",
        "numero": "144",
        "detalle": "Gratuita, las 24 horas, en todo el país.",
    },
    {
        "nombre": "Niñez y adolescencia",
        "numero": "102",
        "detalle": "Gratuita, las 24 horas, en todo el país.",
    },
]

SENALES = [
    "suicid", "matarme", "quitarme la vida", "no quiero vivir", "no quiero estar mas",
    "no vale la pena vivir", "quiero desaparecer", "me quiero morir", "acabar con todo",
    "autolesion", "cortarme", "lastimarme", "me golpea", "me pega", "abuso sexual",
    "violencia familiar", "no aguanto mas",
]


def _normalizar(texto):
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", (texto or "").lower())
        if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.split())


def detectar(*textos):
    """Devuelve las señales encontradas. Lista vacía = sin señales."""
    plano = _normalizar(" ".join(t for t in textos if t))
    return [s for s in SENALES if s in plano]


def texto_derivacion():
    return (
        "Antes de seguir, algo importante: en lo que contó hay un punto que no es materia de "
        "coaching. Nada de esto es un diagnóstico clínico ni una evaluación de su salud, y no "
        "cambia el trabajo que veníamos haciendo. Si en algún momento aparece la idea de "
        "lastimarse, de desaparecer o de que no vale la pena seguir, hay personas preparadas para "
        "escuchar en el acto: 911 si el peligro es inmediato; 148 opción 0 en Mendoza, gratuita y "
        "las 24 horas; 0800 345 1435 en todo el país, de 8 a 24. Pedir esa ayuda no interrumpe su "
        "proceso: lo cuida."
    )
