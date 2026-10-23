"""Secuencia de seguimiento después del diagnóstico.

Cuatro correos en doce días. Nada de descuentos ni urgencia falsa: cada uno propone un ejercicio
concreto y deja la puerta abierta al informe completo. Se corta si la persona se registra o pide
no recibir más.
"""

PASOS = {
    1: {
        "dia": 1,
        "asunto": "Lo que dejó escrito, leído dos veces",
        "cuerpo": (
            "Ayer escribió algo que quizás no había dicho en voz alta.\n\n"
            "Hay una diferencia entre lo que pasó y lo que usted concluyó que pasó. En su "
            "diagnóstico aparece esa diferencia: un hecho —una reunión, un silencio, una frase— y "
            "una conclusión que se repite como si fuera parte del hecho.\n\n"
            "Ejercicio de diez minutos: vuelva a leer lo que escribió y separe las dos columnas. "
            "A la izquierda, lo que cualquiera podría filmar. A la derecha, lo que usted interpretó. "
            "No corrija la interpretación: solo distíngala.\n\n"
            "Ese es el primer movimiento del trabajo ontológico, y es el que hace posible todo lo "
            "demás."
        ),
    },
    2: {
        "dia": 3,
        "asunto": "La conversación que está evitando",
        "cuerpo": (
            "En sus respuestas hay alguien con quien no está hablando de algo importante.\n\n"
            "No hace falta valentía para tener esa conversación. Hace falta tenerla escrita "
            "primero. Escriba tres frases, en este orden: el hecho concreto, el efecto que tuvo en "
            "usted, y el pedido. Sin adjetivos sobre la otra persona y sin explicar por qué tiene "
            "razón.\n\n"
            "Si le sale una cuarta frase justificando lo que dijo, bórrela: eso es el juicio "
            "defendiéndose.\n\n"
            "El informe completo dedica una sección entera a estas conversaciones y arma el plan de "
            "treinta días alrededor de una sola, la que más destraba."
        ),
    },
    3: {
        "dia": 7,
        "asunto": "El costo de sostener el patrón",
        "cuerpo": (
            "Sostener una forma de mirar tiene un precio, y casi nunca se paga en el momento: se "
            "paga en decisiones que no se toman.\n\n"
            "Haga la cuenta de esta semana. ¿Qué no pidió? ¿Qué fecha no acordó? ¿Qué conversación "
            "quedó para «cuando sea el momento»? No es un reproche: es información. El patrón "
            "protege algo, y mientras no sepa qué protege, va a seguir eligiéndolo.\n\n"
            "Cuando quiera ver ese mecanismo escrito, con sus propias palabras y un plan concreto "
            "de treinta días, el informe completo está a un registro de distancia."
        ),
    },
    4: {
        "dia": 12,
        "asunto": "Una última cosa antes de cerrar",
        "cuerpo": (
            "Le escribo por última vez sobre esto.\n\n"
            "Un diagnóstico breve muestra el patrón. Un proceso lo corre de lugar: nueve secciones, "
            "un plan de treinta días con criterios de cumplimiento, y la posibilidad de pedir otro "
            "informe cuando cambia algo, corrigiendo lo que no le representó.\n\n"
            "Si hoy no es el momento, está bien. Guarde este correo y vuelva cuando lo sea. Y si "
            "en algún momento siente que esto excede lo que un coaching puede darle, hay "
            "profesionales verificados en la red y líneas de ayuda abiertas las veinticuatro horas.\n\n"
            "Gracias por escribir con honestidad. No es poco."
        ),
    },
}

DIAS = {paso: datos["dia"] for paso, datos in PASOS.items()}
