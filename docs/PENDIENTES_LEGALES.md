# Pendientes legales y de privacidad

Decisiones tomadas y cosas que quedaron para más adelante, con el motivo y el
disparador que las vuelve urgentes.

## Diferidos por decisión del titular

### 1. Inscripción de la base de datos en el RNBD
**Qué.** Inscribir la base en el Registro Nacional de Bases de Datos de la
Agencia de Acceso a la Información Pública (art. 21, Ley 25.326).
**Cuándo.** Cuando el proyecto tenga volumen sostenido de usuarios, no antes.
**Por qué no ahora.** Es un trámite con costo y obligaciones de actualización
anual; con pocos usuarios el riesgo es bajo y la carga administrativa no.
**Disparador sugerido.** Primeros cien usuarios activos o primera contratación
paga, lo que ocurra antes.

### 2. Identidad del titular en los términos
**Qué.** Nombre o razón social y CUIT del responsable, en la sección 2 del texto
legal. Hoy dice «el titular del sitio».
**Cuándo.** Al habilitar el modo compra (`PAGOS_ACTIVOS=True`).
**Por qué.** Sin facturación no hay titular definido: falta decidir si factura
la persona física, un monotributo propio o una sociedad.

## Pendientes técnicos con impacto legal

### 3. Formulario del botón de arrepentimiento
La Resolución 424/2020 prevé un botón con formulario propio y acuse. Hoy el
enlace abre un correo. Armar `/arrepentimiento/` con formulario, registro de la
solicitud y correo automático.

### 4. Proveedor de IA para los informes
Hoy los informes usan DeepSeek (servidores en China, retención mientras exista
la cuenta, entrenamiento declarado). El texto sale seudonimizado, pero la
transferencia sigue existiendo. Migrar los informes a un proveedor que no
entrene con datos de API y firme tratamiento; dejar DeepSeek solo para contenido
público (Instagram), donde no hay datos de personas.

### 5. Cifrado del disco del servidor
El volumen de Postgres está en un ext4 sin LUKS. Las copias de seguridad sí van
cifradas. Evaluar cifrado de disco o, al menos, restringir el acceso físico.

### 6. IP del diagnóstico: hash en lugar del valor
Guardar un HMAC con clave en vez de la IP, para conservar el límite de cinco por
hora sin almacenar un dato identificatorio. Requiere clave secreta; un hash
común no sirve porque el espacio IPv4 es reversible.

### 7. Registro de accesos a informes
No queda constancia de qué administrador leyó qué informe. Agregar registro de
lectura y mostrarlo en la cuenta del consultante.

### 8. Vencimiento de informes y respuestas
Hoy se conservan mientras la cuenta exista. Definir plazo de inactividad
(sugerido: veinticuatro meses) con aviso previo por correo.

## Cómo se refleja en el texto legal

Las secciones 11 (planes y renovación) y 13 (arrepentimiento) cambian según
`PAGOS_ACTIVOS`: mientras los cobros estén apagados, el texto dice que no hay
contrataciones ni débitos, y no promete renovación automática.
