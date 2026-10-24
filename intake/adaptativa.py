"""Segunda ronda de la entrevista: cinco repreguntas armadas sobre lo que la persona escribió.

Reglas de diseño, en este orden:
1. Solo se pregunta por hechos: qué pasó, cuándo, quién, qué se dijo, qué se hizo.
2. Nunca se interpreta ni se nombra una emoción que la persona no nombró.
3. Se eligen los bloques donde la respuesta quedó más corta o más evasiva.
4. La ronda es opcional: si la persona la saltea, el informe se genera igual.
"""

import json
import logging
import re

from django.conf import settings
from django.utils import timezone

from reports import ai
from reports.engine import calcular_costo

from . import questions as Q
from .models import Entrevista

log = logging.getLogger(__name__)

MAXIMO = 5

SISTEMA = """Usted diseña la segunda ronda de una entrevista de coaching ontológico.

Recibe las respuestas de la primera ronda, escritas por una persona adulta de Argentina. Su tarea \
es elegir hasta cinco repreguntas que permitan llegar a hechos concretos donde la primera ronda \
quedó en generalidades.

Reglas no negociables:
- Pregunte por hechos: qué pasó, cuándo, quién estaba, qué se dijo exactamente, qué hizo usted.
- No interprete, no diagnostique, no sugiera causas, no nombre emociones que la persona no nombró.
- No repita nada que ya esté respondido.
- Una repregunta por hueco. Priorice los bloques con respuestas más cortas o más vagas.
- Trato de usted, sin jerga, máximo 25 palabras por pregunta.
- La pregunta se lee sola, sin contexto: no use «como dijo antes» ni «respecto de lo anterior».

Devuelva SOLO un arreglo JSON, sin texto antes ni después, con hasta cinco objetos así:
[{"key": "slug-corto-en-minusculas", "pregunta": "¿...?", "motivo": "por qué vale la pena preguntarlo, en una frase"}]

Si no hay nada que valga la pena preguntar, devuelva [].
"""


def variante_para(user):
    """Variante del diseño. Con INTAKE_AB definido se reparte por usuario; si no, la actual."""
    opciones = [v.strip() for v in (settings.INTAKE_AB or "").split(",") if v.strip()]
    if len(opciones) >= 2:
        return opciones[user.pk % len(opciones)]
    return settings.INTAKE_VARIANTE_ACTUAL


def entrevista_de(user, crear=True):
    actual = Entrevista.objects.filter(user=user).order_by("-iniciada").first()
    if actual or not crear:
        return actual
    return Entrevista.objects.create(user=user, variante=variante_para(user))


def _material(user):
    respuestas = Q.respuestas(user)
    lineas, flacos = [], []
    for bloque in Q.BLOCKS:
        items = [(q["label"], (respuestas.get(q["key"]) or "").strip()) for q in bloque["questions"]]
        contestadas = [i for i in items if i[1]]
        if not contestadas:
            continue
        promedio = sum(len(v) for _, v in contestadas) / len(contestadas)
        if promedio < 180:
            flacos.append(f"{bloque['titulo']} ({promedio:.0f} caracteres de promedio)")
        lineas.append(f"\n[{bloque['titulo']}]")
        for pregunta, valor in items:
            if valor:
                lineas.append(f"- {pregunta}: {valor[:600]}")
    return "\n".join(lineas), flacos


def _limpiar(texto):
    texto = (texto or "").strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.MULTILINE).strip()
    inicio = texto.find("[")
    fin = texto.rfind("]")
    if inicio == -1 or fin == -1:
        return []
    try:
        datos = json.loads(texto[inicio:fin + 1])
    except json.JSONDecodeError:
        return []
    limpias, vistos = [], set()
    for item in datos if isinstance(datos, list) else []:
        if not isinstance(item, dict):
            continue
        pregunta = (item.get("pregunta") or "").strip()
        clave = (item.get("key") or "").strip().lower()
        clave = re.sub(r"[^a-z0-9-]+", "-", clave).strip("-")[:60]
        pregunta = " ".join(pregunta.split())
        if not pregunta or not clave or clave in vistos:
            continue
        if len(pregunta) > 240:
            pregunta = pregunta[:240].rsplit(" ", 1)[0] + "?"
        vistos.add(clave)
        limpias.append({
            "key": clave,
            "pregunta": pregunta,
            "motivo": " ".join((item.get("motivo") or "").split())[:200],
            "respuesta": "",
        })
        if len(limpias) >= MAXIMO:
            break
    return limpias


def generar(user, forzar=False):
    """Genera y guarda la ronda adaptativa. Devuelve (entrevista, error)."""
    entrevista = entrevista_de(user)
    if entrevista is None:
        return None, "sin entrevista"
    if entrevista.repreguntas and not forzar:
        return entrevista, ""

    material, flacos = _material(user)
    if not material.strip():
        return entrevista, "sin respuestas"

    partes = [
        "Entrevista de primera ronda:",
        material,
    ]
    if flacos:
        partes.append("\nBloques con respuestas breves o generales:\n- " + "\n- ".join(flacos))
    partes.append("\nDevuelva el arreglo JSON con las repreguntas.")

    try:
        texto, uso = ai.completar(SISTEMA, "\n".join(partes), max_tokens=1200)
    except ai.AIUnavailable as exc:
        log.warning("ronda adaptativa sin motor: %s", exc)
        return entrevista, str(exc)

    repreguntas = _limpiar(texto)
    entrevista.repreguntas = repreguntas
    entrevista.generadas_en = timezone.now()
    entrevista.tokens_in = uso["in"]
    entrevista.tokens_out = uso["out"]
    entrevista.costo_usd = calcular_costo(uso["in"], uso["out"], uso["cache"])
    entrevista.save(update_fields=["repreguntas", "generadas_en", "tokens_in",
                                   "tokens_out", "costo_usd"])
    return entrevista, ""


def texto_para_informe(user):
    """Las repreguntas contestadas, en texto, para el prompt del informe."""
    entrevista = entrevista_de(user, crear=False)
    if not entrevista or not entrevista.repreguntas:
        return ""
    lineas = []
    for item in entrevista.repreguntas:
        respuesta = (item.get("respuesta") or "").strip()
        if not respuesta:
            continue
        lineas.append(f"- {item['pregunta']}\n  {respuesta[:settings.AI_MAX_ANSWER_CHARS]}")
    return "\n".join(lineas)


def guardar_respuestas(entrevista, datos):
    """Guarda lo que escribió la persona y devuelve cuántas quedaron contestadas."""
    repreguntas = list(entrevista.repreguntas or [])
    for item in repreguntas:
        valor = (datos.get(item["key"]) or "").strip()
        item["respuesta"] = valor
    entrevista.repreguntas = repreguntas
    entrevista.save(update_fields=["repreguntas"])
    return entrevista.contestadas
