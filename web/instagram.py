"""Publicación en Instagram por la API oficial (Instagram Login).

No usa contraseñas: solo el token de larga duración que vive en el entorno.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://graph.instagram.com/v21.0"


class InstagramError(Exception):
    pass


def _token():
    token = (os.environ.get("IG_TOKEN") or "").strip()
    if not token:
        raise InstagramError("Falta IG_TOKEN en el entorno")
    return token


def _llamar(metodo, ruta, **parametros):
    parametros["access_token"] = _token()
    datos = urllib.parse.urlencode(parametros).encode()
    if metodo == "GET":
        url = f"{BASE}/{ruta}?{datos.decode()}"
        pedido = urllib.request.Request(url, method="GET")
    else:
        pedido = urllib.request.Request(f"{BASE}/{ruta}", data=datos, method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=60) as respuesta:
            return json.loads(respuesta.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            detalle = json.loads(exc.read().decode())
            mensaje = detalle.get("error", {}).get("message", str(exc))
        except Exception:
            mensaje = str(exc)
        raise InstagramError(f"{exc.code}: {mensaje}") from exc


def id_cuenta():
    """El id propio de la cuenta. Se consulta siempre: el del .env puede ser otro."""
    return _llamar("GET", "me", fields="id,username")["id"]


def crear_contenedor(imagen_url, texto, cuenta=None):
    cuenta = cuenta or id_cuenta()
    datos = _llamar("POST", f"{cuenta}/media", image_url=imagen_url, caption=texto)
    return datos["id"]


def esperar_listo(contenedor, intentos=20, pausa=3):
    for _ in range(intentos):
        datos = _llamar("GET", contenedor, fields="status_code,status")
        estado = datos.get("status_code")
        if estado == "FINISHED":
            return True
        if estado == "ERROR":
            raise InstagramError(f"El contenedor falló: {datos.get('status')}")
        time.sleep(pausa)
    raise InstagramError("El contenedor no terminó a tiempo")


def publicar(contenedor, cuenta=None):
    cuenta = cuenta or id_cuenta()
    datos = _llamar("POST", f"{cuenta}/media_publish", creation_id=contenedor)
    return datos["id"]


def datos_publicacion(media_id):
    return _llamar("GET", media_id, fields="id,permalink,timestamp,media_type,caption")


def limite():
    cuenta = id_cuenta()
    datos = _llamar("GET", f"{cuenta}/content_publishing_limit", fields="quota_usage,config")
    return datos.get("data", [{}])[0]
