"""Estructura de la entrevista de intake.

Cada bloque es una dimensión del observador que se quiere relevar. El orden
importa: primero contexto, después historia, vínculos, trabajo, cuerpo y
finalmente juicios y objetivo. Las preguntas son deliberadamente abiertas:
el valor del informe depende de la materia prima.
"""

MINIMO_PARA_INFORME = 20

BLOCKS = [
    {
        "slug": "contexto",
        "titulo": "Su situación hoy",
        "intro": "Empecemos por lo concreto. No hay respuestas correctas: hay respuestas útiles.",
        "questions": [
            {"key": "contexto_nombre", "label": "¿Cómo le gusta que lo llamen?",
             "type": "text", "help": "El nombre con el que quiere ser tratado en el informe."},
            {"key": "contexto_edad", "label": "¿Qué edad tiene?", "type": "text"},
            {"key": "contexto_lugar", "label": "¿Dónde vive y con quién?",
             "type": "long", "help": "Ciudad, tipo de hogar, quiénes comparten su día a día."},
            {"key": "contexto_ocupacion", "label": "¿A qué se dedica hoy?",
             "type": "long", "help": "Ocupación, rol, desde cuándo, si es lo que esperaba."},
            {"key": "contexto_dia", "label": "Describa un día típico, de la mañana a la noche.",
             "type": "long", "help": "Horarios, obligaciones, tiempos muertos, pantallas."},
            {"key": "contexto_energia", "label": "¿Qué parte del día le da energía y cuál se la quita?",
             "type": "long"},
        ],
    },
    {
        "slug": "historia",
        "titulo": "Su historia y el quiebre",
        "intro": "El quiebre es la situación que interrumpe lo que usted daba por sentado. Cuanto más concreto, mejor.",
        "questions": [
            {"key": "historia_quiebre", "label": "¿Qué situación lo trae a este proceso? Cuente el episodio concreto.",
             "type": "long", "help": "Qué pasó, cuándo, quién estaba, qué dijo usted."},
            {"key": "historia_duracion", "label": "¿Hace cuánto ocurre y qué intentó hasta ahora?",
             "type": "long"},
            {"key": "historia_previos", "label": "¿Hizo terapia, coaching u otros procesos? ¿Cómo terminaron?",
             "type": "long", "help": "No hace falta el detalle clínico: interesa qué le sirvió y qué no."},
            {"key": "historia_familia", "label": "¿Cómo era su familia cuando era chico? ¿Qué se podía decir y qué no?",
             "type": "long"},
            {"key": "historia_exito", "label": "¿Qué le enseñaron sobre el éxito, el trabajo y el dinero?",
             "type": "long"},
            {"key": "historia_orgullo", "label": "¿De qué se siente orgulloso y de qué prefiere no hablar?",
             "type": "long"},
        ],
    },
    {
        "slug": "vinculos",
        "titulo": "Vínculos",
        "intro": "Los juicios maestros se sostienen en conversaciones que no se tuvieron.",
        "questions": [
            {"key": "vinculos_pareja", "label": "¿Cómo es su situación de pareja hoy?",
             "type": "long", "help": "Si no tiene pareja, cuente cómo vive la soledad o la compañía."},
            {"key": "vinculos_conflicto", "label": "¿Con quién tiene el conflicto que más se repite? ¿Qué pasa?",
             "type": "long"},
            {"key": "vinculos_silencio", "label": "¿Qué no le puede decir a esa persona?",
             "type": "long", "help": "Escríbalo como se lo diría, sin corregirlo."},
            {"key": "vinculos_apoyo", "label": "¿A quién recurre cuando algo le duele?",
             "type": "long"},
            {"key": "vinculos_limites", "label": "¿Qué le cuesta pedir y qué le cuesta negar?",
             "type": "long"},
        ],
    },
    {
        "slug": "trabajo",
        "titulo": "Trabajo y dinero",
        "intro": "El trabajo es donde suele hacerse visible el ciclo de las promesas.",
        "questions": [
            {"key": "trabajo_rol", "label": "¿Cuál es su rol y qué esperan de usted?",
             "type": "long"},
            {"key": "trabajo_friccion", "label": "¿Qué situación laboral se repite y lo desgasta?",
             "type": "long"},
            {"key": "trabajo_dinero", "label": "¿Cómo se lleva con el dinero? ¿Qué le genera?",
             "type": "long"},
            {"key": "trabajo_futuro", "label": "¿Cómo imagina su trabajo en cinco años?",
             "type": "long"},
        ],
    },
    {
        "slug": "cuerpo",
        "titulo": "Emoción y cuerpo",
        "intro": "La emoción no es lo que le pasa: es lo que lo dispone a la acción.",
        "questions": [
            {"key": "cuerpo_emocion", "label": "¿Qué emoción predomina en las últimas semanas?",
             "type": "long", "help": "Bronca, miedo, tristeza, entusiasmo, resignación, otra."},
            {"key": "cuerpo_sensacion", "label": "¿Dónde la siente en el cuerpo?",
             "type": "long", "help": "Pecho, garganta, estómago, mandíbula, espalda."},
            {"key": "cuerpo_sueno", "label": "¿Cómo duerme y cómo amanece?", "type": "long"},
            {"key": "cuerpo_evita", "label": "¿Qué evita hacer y qué hace en su lugar?",
             "type": "long", "help": "Procrastinación, pantalla, trabajo de más, silencio."},
            {"key": "cuerpo_descarga", "label": "¿Qué hace para descargar tensión?", "type": "long"},
        ],
    },
    {
        "slug": "juicios",
        "titulo": "Juicios, promesas y declaraciones",
        "intro": "Acá está el núcleo del trabajo ontológico. Responda con la primera frase que le venga, sin pulirla.",
        "questions": [
            {"key": "juicios_yo", "label": "Complete: «Yo soy…». ¿Qué juicio repite sobre usted?",
             "type": "long"},
            {"key": "juicios_otros", "label": "Complete: «La gente es…».", "type": "long"},
            {"key": "juicios_mundo", "label": "Complete: «Las cosas siempre…».", "type": "long"},
            {"key": "promesas_incumplidas", "label": "¿Qué prometió y no cumplió?",
             "type": "long", "help": "A otros y a usted mismo."},
            {"key": "promesas_silencio", "label": "¿Qué no se anima a declarar en voz alta?",
             "type": "long"},
            {"key": "juicios_costo", "label": "¿Qué le costó sostener esos juicios?",
             "type": "long", "help": "Oportunidades, vínculos, salud, decisiones que no tomó."},
        ],
    },
    {
        "slug": "objetivo",
        "titulo": "Hacia dónde",
        "intro": "Un objetivo sin indicador es un deseo. Vamos a convertirlo en algo verificable.",
        "questions": [
            {"key": "objetivo_90", "label": "¿Qué quiere lograr en los próximos 90 días, en concreto?",
             "type": "long"},
            {"key": "objetivo_medida", "label": "¿Cómo sabrá que funcionó?",
             "type": "long", "help": "Qué podría ver, medir o escuchar distinto."},
            {"key": "objetivo_soltar", "label": "¿Qué está dispuesto a soltar para lograrlo?",
             "type": "long"},
            {"key": "objetivo_otros", "label": "¿A quién afecta este cambio?", "type": "long"},
            {"key": "objetivo_carta", "label": "Escriba libremente lo que no le preguntamos.",
             "type": "long", "help": "Este espacio suele ser el más productivo del informe."},
        ],
    },
]

FLAT = {q["key"]: {**q, "bloque": b["slug"]} for b in BLOCKS for q in b["questions"]}
TOTAL = len(FLAT)

# Señales que exigen derivar a ayuda profesional en lugar de seguir el proceso.
SENALES_RIESGO = [
    "suicid", "matarme", "quitarme la vida", "no quiero vivir", "no vale la pena vivir",
    "autolesion", "cortarme", "me golpea", "me pega", "abuso sexual", "violencia familiar",
]


def respuestas(user):
    return {a.key: a.value.strip() for a in user.answers.all() if a.value and a.value.strip()}


def progress(user):
    contestadas = len(respuestas(user))
    pct = round(100 * contestadas / TOTAL) if TOTAL else 0
    return contestadas, TOTAL, pct


def estadisticas(user):
    r = respuestas(user)
    filas = []
    for b in BLOCKS:
        hechas = sum(1 for q in b["questions"] if r.get(q["key"]))
        filas.append({
            "slug": b["slug"], "titulo": b["titulo"],
            "hechas": hechas, "total": len(b["questions"]),
            "completo": hechas == len(b["questions"]),
        })
    return filas


def bloques_incompletos(user):
    r = respuestas(user)
    faltan = []
    for b in BLOCKS:
        pendientes = [q for q in b["questions"] if not r.get(q["key"])]
        if pendientes:
            faltan.append({"slug": b["slug"], "titulo": b["titulo"], "faltan": len(pendientes)})
    return faltan


def alertas_riesgo(user):
    texto = " ".join(respuestas(user).values()).lower()
    return [s for s in SENALES_RIESGO if s in texto]
