"""Orquestador de informes: arma el contexto, elige motor y persiste el resultado."""
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.db.models import Max

from intake import questions as Q

from . import ai
from .models import Report

logger = logging.getLogger(__name__)

ORDEN_IA = [
    "Lectura del observador",
    "El quiebre que lo trajo",
    "Juicios maestros",
    "Lenguaje, emoción y cuerpo",
    "Promesas y compromisos",
    "El costo del patrón",
    "Declaraciones para una nueva observación",
    "Plan de 30 días",
    "Preguntas para profundizar",
]


def _cita(texto, limite=320):
    texto = " ".join((texto or "").split())
    if not texto:
        return ""
    texto = texto.rstrip(" .,;:")
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(" ,.;:") + " […]"


def _markdown_plano(secciones):
    return "\n\n".join(f"## {s['titulo']}\n\n{s['cuerpo']}" for s in secciones)


def _entrevista_texto(ctx):
    """Transcripción compacta: cada respuesta recortada y un tope total de caracteres.

    Va primero en el prompt (prefijo estable) para que DeepSeek la tome de su caché
    automática cuando el mismo usuario pide un segundo informe.
    """
    lineas = []
    for bloque in ctx["bloques"]:
        items = [(p, r) for p, r in bloque["items"] if r]
        if not items:
            continue
        lineas.append(f"\n[{bloque['titulo']}]")
        for pregunta, respuesta in items:
            recorte = respuesta[:settings.AI_MAX_ANSWER_CHARS]
            if len(respuesta) > len(recorte):
                recorte += " […]"
            lineas.append(f"- {pregunta[:80]}: {recorte}")
    texto = "\n".join(lineas)
    if len(texto) > settings.AI_MAX_INPUT_CHARS:
        texto = texto[:settings.AI_MAX_INPUT_CHARS] + "\n[entrevista recortada]"
    return texto


def _resumen_informe(informe):
    if not informe:
        return ""
    partes = []
    for seccion in informe.secciones:
        cuerpo = " ".join((seccion.get("cuerpo") or "").split())[:320]
        partes.append(f"- {seccion['titulo']}: {cuerpo}")
    return "\n".join(partes)


def es_hora_pico(momento=None):
    momento = momento or datetime.now(timezone.utc)
    return momento.weekday() < 5 and (1 <= momento.hour < 4 or 6 <= momento.hour < 10)


def calcular_costo(tokens_in, tokens_out, tokens_cache=0, cuando=None, modelo=None):
    """Costo en USD según el modelo usado, su caché y la tarifa de hora pico."""
    precios = settings.AI_PRECIOS.get(modelo or settings.AI_MODEL, {
        "in": settings.AI_PRICE_IN, "out": settings.AI_PRICE_OUT,
        "cache": settings.AI_PRICE_CACHE_IN})
    multiplicador = settings.AI_PRICE_PEAK_MULT if es_hora_pico(cuando) else 1.0
    cache = min(tokens_cache, tokens_in)
    sin_cache = max(tokens_in - cache, 0)
    costo = (
        sin_cache * precios["in"]
        + cache * precios["cache"]
        + tokens_out * precios["out"]
    ) * multiplicador / 1_000_000
    return round(costo, 5)


def _premium_usados(user):
    from .models import Report

    hoy = timezone_nowar()
    return Report.objects.filter(
        user=user, model_name=settings.AI_MODEL_PREMIUM,
        created_at__year=hoy.year, created_at__month=hoy.month).count()


def gasto_mes(user=None):
    """Gasto en USD del mes en curso, total o de un usuario."""
    from django.db.models import Sum

    from .models import Report

    hoy = timezone_nowar()
    consulta = Report.objects.filter(
        engine="ia", created_at__year=hoy.year, created_at__month=hoy.month)
    if user is not None:
        consulta = consulta.filter(user=user)
    return float(consulta.aggregate(total=Sum("costo_usd"))["total"] or 0)


def puede_usar_ia(user):
    """Devuelve (permitido, motivo). Protege el presupuesto antes de llamar a la API."""
    if gasto_mes() >= settings.AI_PRESUPUESTO_USD:
        return False, "presupuesto mensual del sistema agotado"
    if gasto_mes(user) >= settings.AI_LIMITE_USUARIO_USD:
        return False, "límite mensual del usuario alcanzado"
    return True, ""


def timezone_nowar():
    from django.utils import timezone as tz

    return tz.localtime()


def elegir_modelo(user, ctx):
    """Modelo rápido por defecto; el caro solo donde aporta o el usuario lo paga."""
    from web.models import perfil_de

    perfil = perfil_de(user)
    if not perfil.es_pago:
        return settings.AI_MODEL, "cuenta sin plan pago"
    if perfil.plan_efectivo == "estudio":
        return settings.AI_MODEL_PREMIUM, "plan Estudio"
    if ctx["anterior"] is None:
        return settings.AI_MODEL_PREMIUM, "primer informe del plan pago"
    fb = ctx["feedback"]
    if fb and fb.resonancia <= 2 and _premium_usados(user) < settings.AI_PREMIUM_CUPO:
        return settings.AI_MODEL_PREMIUM, "devolución baja: reintento con más capacidad"
    return settings.AI_MODEL, "plan Profundo dentro de cuota"


def contexto(user):
    from web.models import Profile

    respuestas = Q.respuestas(user)
    nombre_perfil = Profile.objects.filter(user=user).values_list("nombre", flat=True).first() or ""
    anterior = user.reports.order_by("-numero").first()
    feedback = anterior.feedbacks.order_by("-created_at").first() if anterior else None
    bloques = [
        {"titulo": b["titulo"], "items": [(q["label"], respuestas.get(q["key"], "")) for q in b["questions"]]}
        for b in Q.BLOCKS
    ]
    ctx = {
        "nombre": (nombre_perfil or user.email.split("@")[0]).strip(),
        "respuestas": respuestas,
        "bloques": bloques,
        "respondidas": len(respuestas),
        "total": Q.TOTAL,
        "anterior": anterior,
        "anterior_resumen": _resumen_informe(anterior),
        "feedback": feedback,
        "alertas": Q.alertas_riesgo(user),
        "faltantes": [q["label"] for q in Q.FLAT.values() if not respuestas.get(q["key"])],
    }
    ctx["entrevista_texto"] = _entrevista_texto(ctx)
    return ctx


def parse_secciones(markdown):
    secciones, actual, buffer = [], None, []
    for linea in (markdown or "").replace("\r\n", "\n").split("\n"):
        if linea.startswith("## "):
            if actual:
                secciones.append({"titulo": actual, "cuerpo": "\n".join(buffer).strip()})
            actual, buffer = linea[3:].strip(), []
        elif actual is not None:
            buffer.append(linea)
    if actual:
        secciones.append({"titulo": actual, "cuerpo": "\n".join(buffer).strip()})
    return [s for s in secciones if s["cuerpo"]]


# --------------------------------------------------------------- motor local

def _riesgo(alertas):
    from web.ayuda import texto_derivacion

    return (
        "**Advertencia de alcance.** En sus respuestas aparecen señales que exceden el coaching. "
        "Este informe no es una intervención en crisis ni un tratamiento. " + texto_derivacion()
    )


def _lectura(ctx):
    r, n = ctx["respuestas"], ctx["nombre"]
    quiebre = _cita(r.get("historia_quiebre", ""), 300)
    emocion = _cita(r.get("cuerpo_emocion", ""), 160)
    juicio = _cita(r.get("juicios_yo", ""), 160)
    partes = [
        f"{n}, lo que sigue no es un diagnóstico ni una evaluación de su persona: es una lectura "
        f"de cómo está mirando su situación hoy. A esa forma de mirar el coaching ontológico la "
        f"llama «observador»: el conjunto de distinciones, juicios y emociones desde el cual usted "
        f"mira y, por lo tanto, el conjunto de acciones que quedan a su alcance."
    ]
    if quiebre:
        partes.append(
            f"Usted trae un episodio concreto: «{quiebre}». Un quiebre no es un problema: es la "
            f"interrupción de algo que usted daba por sentado. Lo que se rompió no es solo una "
            f"situación, es una manera de explicarse quién es usted en esa situación."
        )
    if emocion and juicio:
        partes.append(
            f"En el relato conviven una emoción dominante —{emocion}— y un juicio que se repite: "
            f"«{juicio}». Los tres elementos rara vez son independientes: la emoción dispone el "
            f"juicio, el juicio recorta lo que usted puede ver y lo que no ve limita lo que se "
            f"anima a hacer. Ahí está el circuito que este informe busca abrir."
        )
    return partes


def _local(ctx):
    r = ctx["respuestas"]
    secciones = []
    if ctx["alertas"]:
        secciones.append({"titulo": "Antes de empezar", "cuerpo": _riesgo(ctx["alertas"])})

    # 1. Lectura
    secciones.append({"titulo": "Lectura del observador", "cuerpo": "\n\n".join(_lectura(ctx))})

    # 2. Quiebre
    q = _cita(r.get("historia_quiebre", ""), 400)
    dur = _cita(r.get("historia_duracion", ""), 300)
    prev = _cita(r.get("historia_previos", ""), 300)
    cuerpo = []
    if q:
        cuerpo.append(
            f"El episodio que usted describe —«{q}»— tiene una propiedad que conviene mirar: no "
            f"es un hecho aislado, es el punto donde una interpretación dejó de funcionar. Eso "
            f"explica por qué el esfuerzo puesto hasta ahora no alcanza: usted intenta resolver "
            f"con las mismas distinciones que produjeron el quiebre."
        )
    if dur:
        cuerpo.append(
            f"Sobre la duración y los intentos previos, usted dice: «{dur}». Vale la pena separar "
            f"dos cosas: lo que pasó (afirmación, verificable) y lo que usted concluyó que pasó "
            f"(juicio, revisable). El costo suele estar en la segunda."
        )
    if prev:
        cuerpo.append(
            f"Respecto de procesos anteriores: «{prev}». Si algo no funcionó, conviene precisar "
            f"qué se esperaba y qué se obtuvo. Ese contraste es información, no fracaso."
        )
    if not cuerpo:
        cuerpo.append(
            "No hay un episodio suficientemente descrito en la entrevista. Sin un hecho concreto, "
            "fecha y personas, el análisis queda en el terreno de la opinión. Complete esa "
            "respuesta antes de dar valor a este informe."
        )
    secciones.append({"titulo": "El quiebre que lo trajo", "cuerpo": "\n\n".join(cuerpo)})

    # 3. Juicios maestros
    jy = _cita(r.get("juicios_yo", ""), 200)
    jo = _cita(r.get("juicios_otros", ""), 200)
    jm = _cita(r.get("juicios_mundo", ""), 200)
    ap = _cita(r.get("historia_exito", ""), 260)
    cuerpo = [
        "Un juicio maestro es una sentencia que usted dio hace tiempo, sobre sí, sobre otros o "
        "sobre el mundo, y que desde entonces actúa como filtro. No se discute: se reconoce y se "
        "somete a prueba."
    ]
    for etiqueta, texto in (("sobre usted", jy), ("sobre los demás", jo), ("sobre el mundo", jm)):
        if texto:
            cuerpo.append(f"Su juicio {etiqueta}: «{texto}». Mientras no se declare como juicio, "
                          f"opera como descripción de la realidad y clausura alternativas.")
    if ap:
        cuerpo.append(
            f"El origen probable está en lo que aprendió temprano: «{ap}». Esa enseñanza fue una "
            f"respuesta razonable a un contexto; la pregunta es si sigue siendo razonable en el suyo."
        )
    if not any((jy, jo, jm)):
        cuerpo.append("No completó las frases de juicio. Sin ellas el informe pierde su eje: son "
                      "las tres respuestas de mayor rendimiento en todo el cuestionario.")
    secciones.append({"titulo": "Juicios maestros", "cuerpo": "\n\n".join(cuerpo)})

    # 4. Lenguaje, emoción y cuerpo
    em = _cita(r.get("cuerpo_emocion", ""), 200)
    se = _cita(r.get("cuerpo_sensacion", ""), 200)
    su = _cita(r.get("cuerpo_sueno", ""), 220)
    ev = _cita(r.get("cuerpo_evita", ""), 240)
    de = _cita(r.get("cuerpo_descarga", ""), 180)
    cuerpo = []
    if em:
        cuerpo.append(f"La emoción predominante que usted nombra es {em}. En la tradición "
                      f"ontológica la emoción no es un estado interno que se padece: es una "
                      f"disposición para la acción. Desde ahí, ciertas acciones se vuelven "
                      f"posibles y otras, literalmente, no.")
    if se:
        cuerpo.append(f"Que la registre en el cuerpo —«{se}»— confirma que no es una idea: es una "
                      f"postura corporal sostenida, y por lo tanto modificable por vía corporal "
                      f"tanto como por vía conversacional.")
    if su:
        cuerpo.append(f"Sobre el descanso: «{su}». El sueño es el primer lugar donde se paga el "
                      f"costo de una emoción sostenida sin descarga.")
    if ev:
        cuerpo.append(f"Lo que evita —«{ev}»— y lo que hace en su lugar forman una dupla "
                      f"observable. La conducta sustituta no es un defecto de carácter: es una "
                      f"protección que usted aprendió a usar.")
    if de:
        cuerpo.append(f"Su válvula de descarga es «{de}». Conviene preguntarse si descarga o "
                      f"apaga la señal.")
    if not cuerpo:
        cuerpo.append("Este bloque quedó vacío. Es el que aporta la evidencia corporal del patrón; "
                      "sin él, el informe se apoya solo en el relato.")
    secciones.append({"titulo": "Lenguaje, emoción y cuerpo", "cuerpo": "\n\n".join(cuerpo)})

    # 5. Promesas
    pi = _cita(r.get("promesas_incumplidas", ""), 300)
    ps = _cita(r.get("promesas_silencio", ""), 300)
    vs = _cita(r.get("vinculos_silencio", ""), 300)
    cuerpo = [
        "El ciclo del compromiso tiene cuatro pasos: se pide, se acepta, se ejecuta y se declara "
        "satisfacción. Cuando uno se saltea, lo que queda no es un incumplimiento aislado: queda "
        "una deuda conversacional."
    ]
    if pi:
        cuerpo.append(f"Usted identifica como promesa incumplida: «{pi}». La pregunta útil no es "
                      f"por qué falló, sino qué prometió sin haber pedido lo necesario para cumplir.")
    if ps:
        cuerpo.append(f"Y hay algo que no declara: «{ps}». Una declaración no dicha sigue operando "
                      f"como si estuviera dicha, pero sin posibilidad de respuesta del otro.")
    if vs:
        cuerpo.append(f"En el vínculo, lo que no puede decir es «{vs}». Ese silencio es el que "
                      f"sostiene el juicio maestro; hablarlo es lo que lo pone en riesgo.")
    secciones.append({"titulo": "Promesas y compromisos", "cuerpo": "\n\n".join(cuerpo)})

    # 6. Costo
    co = _cita(r.get("juicios_costo", ""), 320)
    so = _cita(r.get("objetivo_soltar", ""), 240)
    tf = _cita(r.get("trabajo_friccion", ""), 240)
    cuerpo = []
    if co:
        cuerpo.append(f"El costo que usted reconoce: «{co}». Conviene ponerle números: cuántas "
                      f"decisiones no tomadas, cuántas conversaciones evitadas, cuánto tiempo.")
    if tf:
        cuerpo.append(f"En el trabajo el patrón se repite así: «{tf}». No es casualidad: el mismo "
                      f"observador que evita una conversación personal evita el pedido incómodo "
                      f"en la oficina. Cambia el escenario, no la lógica.")
    if so:
        cuerpo.append(f"Usted anticipa qué tendría que soltar: «{so}». Ese «soltar» suele ser, en "
                      f"los hechos, una conversación y no una renuncia.")
    if not cuerpo:
        cuerpo.append("Sin las respuestas de costo y de trabajo, este apartado queda incompleto. "
                      "El costo es lo que moviliza: sin él, el informe es interesante pero no urgente.")
    secciones.append({"titulo": "El costo del patrón", "cuerpo": "\n\n".join(cuerpo)})

    # 7. Declaraciones
    obj = _cita(r.get("objetivo_90", ""), 240)
    nombre = ctx["nombre"]
    decl = [
        f"«Yo, {nombre}, declaro que “{jy or 'el juicio que vengo repitiendo'}” es un juicio mío y "
        f"no un hecho sobre mí. Me hago cargo de que lo sostengo yo y de que puedo revisarlo.»" if jy
        else f"«Yo, {nombre}, declaro que los juicios que repito sobre mí son interpretaciones y "
             f"no hechos, y me comprometo a registrarlos por escrito durante treinta días.»",
        "«Declaro terminada mi participación en la conversación que no tuve: voy a tenerla, con "
        "hechos, impacto y un pedido concreto, antes de que termine este mes.»",
    ]
    if obj:
        decl.append(f"«Declaro que mi objetivo es {obj}, y que voy a pedir la ayuda que necesito "
                    f"para sostenerlo, en lugar de intentarlo solo.»")
    decl.append("«Declaro que puedo equivocarme en esta lectura y que el próximo informe dirá si "
                "acerté.»")
    cuerpo = [
        "Una declaración no describe el mundo: lo abre. No es un deseo ni una intención; es un "
        "acto que crea un compromiso frente a otros. Estas son las que se desprenden de su "
        "material; léalas en voz alta y quédese solo con las que pueda sostener."
    ] + [f"- {d}" for d in decl]
    secciones.append({"titulo": "Declaraciones para una nueva observación", "cuerpo": "\n\n".join(cuerpo)})

    # 8. Plan
    med = _cita(r.get("objetivo_medida", ""), 220)
    plan = [
        "**Semana 1 — Registro de juicios.** Cada noche anote tres columnas: qué pasó, qué juicio "
        "formuló, qué emoción sintió. Diez minutos. Criterio de cumplimiento: siete registros de "
        "siete días.",
        "**Semana 2 — La conversación pendiente.** Diga lo que escribió en «qué no le puede decir», "
        "con este formato: hecho concreto, impacto en usted, pedido. Criterio: la conversación "
        "ocurre, no que salga bien.",
        f"**Semana 3 — Un pedido laboral.** Formule un pedido explícito sobre «{tf or 'la situación que se repite'}»: "
        "qué necesita, de quién, para cuándo y cómo sabrá que fue aceptado. Criterio: el pedido se "
        "hace por escrito u oralmente, con plazo.",
        f"**Semana 4 — Medición y nuevo informe.** Revise su indicador: «{med or 'cómo sabrá que funcionó'}». "
        "Genere un segundo informe con lo observado y su devolución. Criterio: un informe nuevo "
        "con evidencia de las tres semanas anteriores.",
    ]
    secciones.append({"titulo": "Plan de 30 días", "cuerpo": "\n\n".join(plan)})

    # 9. Preguntas
    preguntas = [
        "¿Qué tendría que ser verdad para que el juicio que repite sobre usted fuera falso?",
        "¿A quién le debe una respuesta desde hace más de un año?",
        "¿Qué está protegiendo con la conducta que llama «procrastinación»?",
        "Si el cambio dependiera de una sola conversación, ¿cuál sería y con quién?",
    ]
    if ctx["faltantes"]:
        preguntas.append(
            f"Quedaron {len(ctx['faltantes'])} preguntas sin responder, entre ellas «{ctx['faltantes'][0]}». "
            f"¿Qué lo llevó a saltearlas?")
    secciones.append({"titulo": "Preguntas para profundizar",
                      "cuerpo": "\n\n".join(f"- {p}" for p in preguntas)})

    # 10. Ajuste por feedback
    fb = ctx.get("feedback")
    if fb:
        cuerpo = [f"Su devolución anterior fue de {fb.resonancia}/5."]
        if fb.aciertos:
            cuerpo.append(f"Lo que le sirvió: «{_cita(fb.aciertos, 300)}». Se conserva como eje del "
                          f"análisis en este informe.")
        if fb.desaciertos:
            cuerpo.append(f"Lo que no le representó: «{_cita(fb.desaciertos, 300)}». Se retira del "
                          f"planteo: si la lectura no le representa, la conversación cambia.")
        if fb.profundizar:
            cuerpo.append(f"Lo que pidió profundizar: «{_cita(fb.profundizar, 300)}». Este informe "
                          f"lo aborda en las secciones de juicios y de plan de acción.")
        secciones.append({"titulo": "Ajustes sobre el informe anterior", "cuerpo": "\n\n".join(cuerpo)})

    return secciones


# --------------------------------------------------------------- generación

def generar(user):
    ctx = contexto(user)
    secciones, motor, modelo = None, "local", ""
    tokens_in = tokens_out = tokens_cache = 0
    elegido, motivo = elegir_modelo(user, ctx)
    logger.info("Modelo para %s: %s (%s)", user.pk, elegido, motivo)

    permitido, bloqueo = puede_usar_ia(user)
    if not permitido:
        logger.warning("Sin llamada a IA para %s: %s", user.pk, bloqueo)

    if ai.disponible() and permitido:
        try:
            texto, usage = ai.generar_informe(ctx, elegido)
            parseadas = parse_secciones(texto)
            if len(parseadas) >= 5:
                secciones, motor, modelo = parseadas, "ia", elegido
                tokens_in, tokens_out = usage["in"], usage["out"]
                tokens_cache = usage.get("cache", 0)
        except ai.AIUnavailable as exc:
            logger.warning("Motor de IA no disponible: %s", exc)

    if not secciones:
        secciones = _local(ctx)
        motor = "local"

    numero = (Report.objects.filter(user=user).aggregate(m=Max("numero"))["m"] or 0) + 1
    costo = calcular_costo(tokens_in, tokens_out, tokens_cache, modelo=modelo) if motor == "ia" else 0

    return Report.objects.create(
        user=user,
        numero=numero,
        titulo=f"Informe ontológico Nº {numero}",
        engine=motor,
        model_name=modelo,
        secciones=secciones,
        cuerpo=_markdown_plano(secciones),
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_cache=tokens_cache,
        costo_usd=costo,
    )
