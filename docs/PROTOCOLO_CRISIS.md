# Protocolo ante señales de riesgo

Documento operativo de Onto. No es un protocolo clínico: define qué hace el sistema, qué hace
una persona y qué no se hace nunca. Debe revisarlo un profesional de la salud mental y un abogado
antes de abrir el servicio al público.

## 1. Principio

Onto escribe informes de coaching ontológico. No diagnostica, no trata y no reemplaza atención
profesional. Cuando aparecen señales de riesgo, la prioridad deja de ser el informe y pasa a ser
la derivación. La derivación **nunca** se cobra ni se monetiza.

## 2. Detección

Dos capas, en este orden:

1. **Palabras clave** (`web/ayuda.py`): ideación suicida, autolesión, violencia, abuso. Se aplica
   sobre todo el texto libre, sin distinguir acentos ni mayúsculas.
2. **Clasificación por IA**: en el mismo llamado que redacta el informe, el modelo evalúa el texto
   y responde `RIESGO` si corresponde. No es una consulta adicional y no agrega costo.

Las señales son indicios, no diagnósticos. Un falso positivo cuesta una página de ayuda; un falso
negativo cuesta mucho más. Ante la duda, se deriva.

## 3. Qué hace el sistema

- **Diagnóstico público**: corta el flujo antes de pedir el correo, muestra las líneas de ayuda, no
  genera informe, no envía correo y **no guarda las respuestas**.
- **Informe pago**: el informe se entrega igual, con un bloque «Antes de empezar» como primera
  sección, en tono cuidado, sin interpretar la crisis. No se cancela el servicio ni se cobra aparte.

## 4. Qué hace una persona del equipo

- Revisar el buzón de contacto dos veces por día, a las 9 y a las 18.
- Si alguien escribe en crisis, responder dentro de las 24 horas con la plantilla de la sección 6.
- No diagnosticar, no interpretar, no dar indicaciones clínicas, no recomendar medicación.
- Ofrecer las líneas y, si la persona lo pide, la derivación a un profesional de la red.
- Si hay peligro inminente y la persona es identificable, llamar al 911. No contactar a terceros
  sin consentimiento, salvo riesgo de vida, y en ese caso dejar registro de por qué.

## 5. Registro

Se registra solo el evento: fecha, canal, si hubo derivación, resultado. **No se guarda el
contenido clínico** de lo que la persona escribió. Retención: 6 meses. Acceso: solo el responsable
del protocolo.

## 6. Plantilla de respuesta

> Gracias por escribirnos y por confiarnos lo que está pasando. Onto escribe informes de coaching
> y no atiende crisis, así que no voy a intentar analizar esto por correo. Si en este momento
> siente que no puede solo, hay personas preparadas para escuchar: 911 si hay peligro inmediato,
> 148 opción 0 en Mendoza (gratuita, 24 horas) y 0800 345 1435 en todo el país (8 a 24). Si querés,
> te pongo en contacto con un profesional de nuestra red, sin costo y sin que eso te comprometa a
> nada. Estoy acá.

## 7. Red de profesionales

- Verificación de matrícula y de seguro de responsabilidad civil antes de listar a alguien.
- Admisión por criterio del equipo, no automática.
- **Sin comisiones por derivación.** Ni Onto cobra al profesional por paciente derivado, ni el
  profesional paga por recibirlo. Los códigos de ética profesional prohíben el pago y la percepción
  de honorarios por derivación, y esa regla también protege la confianza en el servicio.
- Compartir datos de una persona requiere su consentimiento expreso, informado y revocable
  (Ley 25.326, datos sensibles; Ley 26.529, derechos del paciente).

## 8. Revisión

El protocolo y los textos de derivación se revisan cada seis meses, o antes si cambia una línea
telefónica. Las líneas se verifican contra fuentes oficiales: mendoza.gov.ar para el 148 y el
sitio del Centro de Asistencia al Suicida para el 0800 345 1435.

## 9. Marco legal de referencia

- Ley 25.326 de Protección de los Datos Personales: datos sensibles, consentimiento, derechos de
  acceso y supresión.
- Ley 26.529 de Derechos del Paciente: información, consentimiento informado e historia clínica.
- Ley 17.132 y normativa provincial de Mendoza sobre ejercicio profesional.
- Código de Ética de la Federación de Psicólogos de la República Argentina.
