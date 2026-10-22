"""Crea (o recrea) la cuenta de demostración con entrevista completa y un informe generado."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from intake import questions as Q
from intake.models import Answer
from reports import engine
from web.models import perfil_de

EMAIL = "demo@observador.test"
PASSWORD = "Demo2026!"

RESPUESTAS = {
    "contexto_nombre": "Mariana",
    "contexto_edad": "38",
    "contexto_lugar": "Godoy Cruz, Mendoza. Vivo con mi hija de 9 años.",
    "contexto_ocupacion": "Soy contadora en una empresa familiar; hace tres años que no me ascenden.",
    "contexto_dia": "Arranco a las 6:30, colegio, oficina hasta las 18, cena y planillas hasta la medianoche.",
    "contexto_energia": "Me despierta la mañana con mi hija; me apaga la reunión de los martes con mi padre.",
    "historia_quiebre": "En la reunión de socios de junio mi padre presentó un balance que yo había armado y no me nombró. Me quedé callada y después lloré en el auto.",
    "historia_duracion": "Hace tres años que vengo postergando el tema; lo hablé una vez y me dijeron que era sensible.",
    "historia_previos": "Hice terapia dos años por ansiedad. Me ayudó a dormir, no a decir lo que pienso.",
    "historia_familia": "Familia de laburantes. Se hablaba de esfuerzo y no de plata. Las discusiones se resolvían con silencio.",
    "historia_exito": "Me enseñaron que el trabajo dignifica y que reclamar es de mala persona.",
    "historia_orgullo": "Sostuve la empresa cuando mi mamá se enfermó. De eso no hablo con nadie.",
    "vinculos_pareja": "Separada hace cuatro años; buena relación con el papá de mi hija, sin intimidad.",
    "vinculos_conflicto": "Con mi padre, en la empresa. Él decide y yo ejecuto, y después me enojo conmigo.",
    "vinculos_silencio": "Le diría que estoy cansada de ser la que sostiene todo sin reconocimiento.",
    "vinculos_apoyo": "Con mi hermana, pero no le cuento lo de la empresa para no preocuparla.",
    "vinculos_limites": "Me cuesta pedir aumento y me cuesta negarme a cubrir turnos ajenos.",
    "trabajo_rol": "Contadora senior, responsable de todo el cierre contable y de los bancos.",
    "trabajo_friccion": "Asumo tareas que no me corresponden y después las hago mal por cansancio.",
    "trabajo_dinero": "El dinero me da seguridad; hablar de mi sueldo me da vergüenza.",
    "trabajo_futuro": "Me imagino con una consultora propia, con dos clientes y horario propio.",
    "cuerpo_emocion": "Bronca contenida y culpa, alternadas.",
    "cuerpo_sensacion": "Nudo en la garganta y mandíbula apretada al despertar.",
    "cuerpo_sueno": "Duermo cinco horas; me despierto a las 3 con la cabeza en la reunión del martes.",
    "cuerpo_evita": "Evito pedir reuniones; mando mails largos en lugar de hablar.",
    "cuerpo_descarga": "Trabajo de más y como parada.",
    "juicios_yo": "Yo soy la que sostiene, no la que pide.",
    "juicios_otros": "La gente no reconoce lo que hacés por ella.",
    "juicios_mundo": "Las cosas siempre se arreglan solas si uno aguanta.",
    "promesas_incumplidas": "Prometí a mi hija que este año cambiábamos los horarios. Sigue igual.",
    "promesas_silencio": "No me animo a decir que quiero irme de la empresa de mi padre.",
    "juicios_costo": "Tres años sin ascenso, una relación que no empieza y una hija que me ve cansada.",
    "objetivo_90": "Tener una conversación con mi padre sobre mi rol y mi remuneración, con una propuesta escrita.",
    "objetivo_medida": "Habré cumplido si la reunión ocurre, si llevo la propuesta y si salgo con una fecha de respuesta.",
    "objetivo_soltar": "Soltar la idea de que pedir es traicionar a la familia.",
    "objetivo_otros": "A mi padre, mi hermana y mi hija.",
    "objetivo_carta": "Escribo esto un martes a la noche, después de otro cierre. Quiero dejar de ser la que aguanta.",
}


class Command(BaseCommand):
    help = "Crea la cuenta demo con entrevista completa, plan Profundo y un informe generado."

    def handle(self, *args, **options):
        if len(RESPUESTAS) != Q.TOTAL:
            self.stderr.write(
                f"Las respuestas demo ({len(RESPUESTAS)}) no coinciden con las preguntas del "
                f"intake ({Q.TOTAL}). Actualice RESPUESTAS.")
            return

        User = get_user_model()
        User.objects.filter(email=EMAIL).delete()
        user = User.objects.create_user(username=EMAIL, email=EMAIL, password=PASSWORD)
        perfil = perfil_de(user)
        perfil.nombre = "Mariana"
        perfil.plan = "pro"
        perfil.pro_until = timezone.localdate() + timedelta(days=30)
        perfil.consent_at = timezone.now()
        perfil.save()

        for clave, valor in RESPUESTAS.items():
            Answer.objects.update_or_create(user=user, key=clave, defaults={"value": valor})

        informe = engine.generar(user)
        self.stdout.write(self.style.SUCCESS(
            f"Demo lista: {EMAIL} / {PASSWORD} · informe Nº {informe.numero} "
            f"({informe.engine}, {len(informe.secciones)} secciones)"))
