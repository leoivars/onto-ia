import json
import urllib.error
import urllib.request

from django.conf import settings


class AIUnavailable(Exception):
    pass


def disponible():
    return bool(settings.AI_API_KEY)


def _post(url, payload, timeout):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {settings.AI_API_KEY}")
    req.add_header("User-Agent", "Observador/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


SYSTEM = """Usted es un coach ontológico con veinte años de práctica, formado en la tradición de \
Fernando Flores, Rafael Echeverría y Humberto Maturana. Escribe informes de coaching ontológico \
para adultos de Argentina.

Recibe la transcripción completa de una entrevista de intake y debe devolver un informe escrito, \
no una conversación ni un resumen de lo que el consultante ya sabe.

Reglas no negociables:
- Español rioplatense formal. Trate al consultante de «usted». Sin diminutivos y sin tono \
motivacional vacío.
- No diagnostique, no nombre patologías, no indique medicación y no prometa curas ni resultados \
terapéuticos. Usted no reemplaza a un profesional de la salud mental y lo dice cuando corresponde.
- Distinga siempre juicios (opiniones revisables) de afirmaciones (hechos verificables).
- Trabaje con las distinciones ontológicas: observador, quiebre, juicio maestro, declaración, \
promesa, ciclo del compromiso y coherencia entre lenguaje, emoción y cuerpo.
- Cite entre comillas frases textuales del consultante. No invente episodios, nombres ni datos.
- Si falta información, señale el hueco en lugar de rellenarlo.
- No repita los títulos de las secciones dentro del texto.

Extensión total: entre 1200 y 1800 palabras.

Devuelva Markdown con exactamente estos encabezados de nivel 2, en este orden y sin agregar otros:
## Lectura del observador
## El quiebre que lo trajo
## Juicios maestros
## Lenguaje, emoción y cuerpo
## Promesas y compromisos
## El costo del patrón
## Declaraciones para una nueva observación
## Plan de 30 días
## Preguntas para profundizar
"""


def _formatear_entrevista(ctx):  # pragma: no cover - compatibilidad
    return ctx.get("entrevista_texto", "")


def generar_informe(ctx, modelo=None):
    """Devuelve (texto_markdown, usage). Lanza AIUnavailable si no hay motor."""
    if not disponible():
        raise AIUnavailable("Falta AI_API_KEY")

    ctx = {
        "nombre": ctx["nombre"],
        "respondidas": ctx["respondidas"],
        "total": ctx["total"],
        "entrevista_texto": ctx["entrevista_texto"],
        "anterior_resumen": ctx["anterior_resumen"],
        "feedback": ctx["feedback"],
        "alertas": ctx["alertas"],
    }
    partes = [
        f"Consultante: {ctx['nombre']}",
        f"Entrevista de intake ({ctx['respondidas']} respuestas de {ctx['total']}):",
        ctx["entrevista_texto"],
    ]

    if ctx["anterior_resumen"]:
        partes.append("\n### Informe anterior (resumen; no lo repita: profundícelo)")
        partes.append(ctx["anterior_resumen"])

    if ctx.get("feedback"):
        fb = ctx["feedback"]
        partes.append("\n### Devolución del consultante sobre el informe anterior")
        partes.append(f"Resonancia: {fb.resonancia}/5")
        if fb.aciertos:
            partes.append(f"Le sirvió: {fb.aciertos}")
        if fb.desaciertos:
            partes.append(f"No le representó: {fb.desaciertos}")
        if fb.profundizar:
            partes.append(f"Pide profundizar: {fb.profundizar}")
        partes.append("Corrija lo que no le representó y profundice lo pedido. No repita el informe anterior.")

    if ctx.get("alertas"):
        partes.append(
            "\n### Atención\nAparecen señales de riesgo en las respuestas. Incluya una sección breve "
            "al inicio, dentro de «Lectura del observador», recomendando consultar a un profesional "
            "de salud mental y a una línea de ayuda local. No intente intervenir en crisis.")

    payload = {
        "model": modelo or settings.AI_MODEL,
        "temperature": 0.7,
        "max_tokens": settings.AI_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "\n".join(partes)},
        ],
    }
    try:
        data = _post(f"{settings.AI_BASE_URL.rstrip('/')}/chat/completions",
                     payload, settings.AI_TIMEOUT)
        texto = data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, KeyError, IndexError, TimeoutError, json.JSONDecodeError) as exc:
        raise AIUnavailable(str(exc)) from exc

    usage = data.get("usage") or {}
    return texto, {
        "in": int(usage.get("prompt_tokens") or 0),
        "out": int(usage.get("completion_tokens") or 0),
        "cache": int(usage.get("prompt_cache_hit_tokens") or 0),
    }
