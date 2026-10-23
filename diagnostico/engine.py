"""Generación del mini-informe del diagnóstico (3 minutos, ~400 palabras)."""
import logging

from django.conf import settings

from reports import ai

logger = logging.getLogger(__name__)

SISTEMA = """Usted es un coach ontológico con veinte años de práctica, formado en la tradición \
de Fernando Flores, Rafael Echeverría y Humberto Maturana. Escribe un diagnóstico breve para una \
persona que respondió cinco preguntas en un formulario público.

Reglas:
- Español rioplatense formal, trate de «usted». Sin diminutivos ni tono motivacional vacío.
- Escriba en lenguaje común. No use jerga del coaching («observador», «quiebre», «juicio maestro», «declaración»). Si necesita nombrar el patrón, hágalo con palabras de todos los días.
- No diagnostique ni nombre patologías. No prometa resultados ni recomiende medicación.
- Distinga lo que pasó (hecho) de lo que la persona concluyó que pasó (interpretación).
- Cite entre comillas frases textuales de la persona. No invente datos.
- Extensión: 350 a 450 palabras.

Devuelva Markdown con exactamente estos tres encabezados de nivel 2:
## Qué está sosteniendo
## Qué le cuesta
## Una acción para esta semana

La acción debe ser concreta, de menos de una hora, ejecutable en los próximos siete días.
"""


def _prompt(datos):
    lineas = []
    for clave, valor in datos.items():
        lineas.append(f"- {clave}: {valor.strip()[:600]}")
    return "\n".join(lineas)


def _respaldo(datos, nombre=""):
    saludo = f"{nombre}, " if nombre else ""
    quiebre = " ".join((datos.get("situacion") or "").split())[:220]
    juicio = " ".join((datos.get("juicio") or "").split())[:180]
    evita = " ".join((datos.get("evita") or "").split())[:180]
    return (
        f"## Qué está sosteniendo\n\n"
        f"{saludo}el episodio que trae —«{quiebre}»— no es solo una "
        f"situación incómoda: es el punto donde una forma de mirar dejó de funcionar. "
        f"Y esa forma de mirar tiene una frase: «{juicio}». Mientras se repite como si fuera "
        f"un hecho, clausura alternativas.\n\n"
        f"## Qué le cuesta\n\nLo que evita —«{evita}»— no es falta de voluntad. Es la conducta "
        f"que protege ese juicio. El costo aparece en las decisiones que no se toman y en las "
        f"conversaciones que se postergan.\n\n"
        f"## Una acción para esta semana\n\nElija la conversación que viene evitando y escriba, "
        f"en tres frases: el hecho concreto, el impacto que tuvo en usted y el pedido que quiere "
        f"hacer. No la tenga todavía: escríbala. Menos de veinte minutos.\n"
    )


def generar(datos, nombre=""):
    """Devuelve (markdown, motor). Nunca falla: si no hay IA, usa la plantilla."""
    if ai.disponible():
        try:
            prompt = _prompt(datos)
            if nombre:
                prompt = f"Nombre de la persona: {nombre}\n{prompt}"
            texto, usage = ai.completar(
                SISTEMA, prompt, modelo=settings.AI_MODEL, max_tokens=1200)
            if len(texto) > 400:
                return texto, "ia"
        except ai.AIUnavailable as exc:
            logger.warning("Diagnóstico sin IA: %s", exc)
    return _respaldo(datos, nombre), "local"
