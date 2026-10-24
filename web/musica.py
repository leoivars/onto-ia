"""Análisis musical para editar al ritmo.

Se corre en la máquina de trabajo, no en producción: `librosa` no está en la
imagen del servidor. La referencia que se analiza (una grabación de pantalla, un
fragmento) se usa solo para medir y se borra después: nunca se publica ni se
incluye en el video, porque la música la agrega Instagram desde su biblioteca.

Uso típico:
    analizar("referencia.m4a")  → bpm, primer golpe y grilla de tiempos
    cortes(bpm, duracion=8, compas=4) → segundos donde conviene cambiar de plano
"""

from pathlib import Path


def _librosa():
    try:
        import librosa  # noqa: F401
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Falta librosa en este entorno. Instalar con: pip install librosa numpy"
        ) from exc
    import librosa

    return librosa


def analizar(archivo, maximo_segundos=45):
    """Devuelve pulso, primer golpe fuerte y la lista de golpes detectados.

    `maximo_segundos` recorta la referencia: con veinte segundos alcanza y sobra
    para estimar el pulso.
    """
    import numpy as np

    librosa = _librosa()
    ruta = Path(archivo)
    if not ruta.exists():
        raise RuntimeError(f"no existe el archivo: {ruta}")

    señal, frecuencia = librosa.load(str(ruta), sr=22050, mono=True,
                                     duration=maximo_segundos)
    if señal.size == 0:
        raise RuntimeError("el archivo no tiene audio decodificable")

    # Se separa el pulso del resto: en música con voz, el beat tracker se pierde menos
    # si se mira la percusión.
    armonico, percusivo = librosa.effects.hpss(señal)
    tempo, golpes = librosa.beat.beat_track(y=percusivo, sr=frecuencia, units="time")
    bpm = float(np.atleast_1d(tempo)[0]) if np.size(tempo) else 0.0
    golpes = [round(float(g), 3) for g in np.atleast_1d(golpes)]

    # Ajuste fino: se prueban candidatos y se queda el que mejor encaja con los
    # ataques reales. El estimador de librosa erra ~2%, y en 8 segundos eso se nota.
    bpm, fase = _rejilla_fina(señal, frecuencia, bpm)
    if bpm:
        golpes = [round(fase + i * 60.0 / bpm, 3)
                  for i in range(int((len(señal) / frecuencia) / (60.0 / bpm)) + 1)]
        golpes = [g for g in golpes if g <= len(señal) / frecuencia]

    # Los acentos: los golpes con más energía suelen marcar el inicio del compás.
    energia = librosa.feature.rms(y=percusivo, frame_length=2048, hop_length=512)[0]
    tiempos_energia = librosa.frames_to_time(range(len(energia)), sr=frecuencia, hop_length=512)
    acentos = []
    for golpe in golpes:
        cercano = int(np.argmin(np.abs(tiempos_energia - golpe)))
        acentos.append(float(energia[cercano]))
    umbral = (sum(acentos) / len(acentos) * 1.15) if acentos else 0
    inicio_fuerte = next((g for g, a in zip(golpes, acentos) if a >= umbral), golpes[0] if golpes else 0)

    return {
        "bpm": round(bpm, 1),
        "duracion_analizada": round(len(señal) / frecuencia, 2),
        "golpes": golpes,
        "primer_golpe_fuerte": round(float(inicio_fuerte), 3),
        "acentos": [round(a, 4) for a in acentos],
    }


def _rejilla_fina(señal, frecuencia, bpm_inicial):
    """Busca pulso y fase que mejor explican los ataques: rejilla contra energía.

    Devuelve (bpm, fase_en_segundos). Si no encuentra nada mejor que el estimador,
    devuelve el pulso original y fase cero.
    """
    import numpy as np

    librosa = _librosa()
    envolvente = librosa.onset.onset_strength(y=señal, sr=frecuencia)
    tiempos = librosa.frames_to_time(range(len(envolvente)), sr=frecuencia, hop_length=512)
    if len(tiempos) < 4:
        return bpm_inicial, 0.0

    def puntaje(pulso, fase):
        rejilla = np.arange(fase, tiempos[-1], pulso)
        indices = np.searchsorted(tiempos, rejilla)
        indices = np.clip(indices, 0, len(envolvente) - 1)
        return float(np.mean(envolvente[indices]))

    mejor = (bpm_inicial or 120.0, 0.0, -1.0)
    for candidato in np.arange(70.0, 181.0, 0.5):
        pulso = 60.0 / candidato
        for fase in np.arange(0, pulso, 0.01):
            valor = puntaje(pulso, fase)
            if valor > mejor[2]:
                mejor = (candidato, float(fase), valor)
    return round(mejor[0], 1), round(mejor[1], 3)


def cortes(bpm, duracion=8, compas=4, desde=0.0):
    """Segundos donde conviene que cambie algo en pantalla (cada compás o medio compás)."""
    if bpm <= 0:
        raise RuntimeError("sin pulso: no se pueden calcular cortes")
    pulso = 60.0 / bpm
    paso = pulso * compas
    marcas, t = [], desde
    while t < duracion - 0.2:
        marcas.append(round(float(t), 2))
        t += paso
    return marcas


def alinear(golpes, cantidad, desde=0.0):
    """Los `cantidad` golpes más cercanos al inicio, para que cada texto entre en tiempo."""
    if not golpes:
        return [desde + i * 1.0 for i in range(cantidad)]
    utiles = [g for g in golpes if g >= desde]
    if len(utiles) < cantidad:
        # Si faltan golpes, se reparten sobre el intervalo medio detectado.
        intervalo = (utiles[1] - utiles[0]) if len(utiles) > 1 else 1.0
        faltan = cantidad - len(utiles)
        base = utiles[-1] if utiles else desde
        utiles += [base + intervalo * (i + 1) for i in range(faltan)]
    return [round(float(g), 2) for g in utiles[:cantidad]]
