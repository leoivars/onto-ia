"""Render mínimo de Markdown a HTML, sin dependencias externas."""
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe


def _inline(texto):
    t = escape(texto)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    return t


def render(texto):
    bloques, parrafo, items, tipo = [], [], None, None

    def cerrar_parrafo():
        if parrafo:
            bloques.append("<p>" + _inline(" ".join(parrafo)) + "</p>")
            parrafo.clear()

    def cerrar_lista():
        nonlocal items, tipo
        if items is not None:
            bloques.append(
                f"<{tipo}>" + "".join(f"<li>{_inline(i)}</li>" for i in items) + f"</{tipo}>")
            items, tipo = None, None

    for cruda in (texto or "").split("\n"):
        linea = cruda.strip()
        if not linea:
            cerrar_parrafo()
            cerrar_lista()
            continue
        if linea.startswith("#### "):
            cerrar_parrafo(); cerrar_lista()
            bloques.append(f"<h4>{_inline(linea[5:])}</h4>")
            continue
        if linea.startswith("### "):
            cerrar_parrafo(); cerrar_lista()
            bloques.append(f"<h4>{_inline(linea[4:])}</h4>")
            continue
        m = re.match(r"^[-*]\s+(.*)$", linea)
        if m:
            cerrar_parrafo()
            if tipo != "ul":
                cerrar_lista(); tipo, items = "ul", []
            items.append(m.group(1))
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", linea)
        if m:
            cerrar_parrafo()
            if tipo != "ol":
                cerrar_lista(); tipo, items = "ol", []
            items.append(m.group(1))
            continue
        if linea.startswith("> "):
            cerrar_parrafo(); cerrar_lista()
            bloques.append(f"<blockquote>{_inline(linea[2:])}</blockquote>")
            continue
        cerrar_lista()
        parrafo.append(linea)

    cerrar_parrafo()
    cerrar_lista()
    return mark_safe("\n".join(bloques))
