# Bloque de Caddy para onto.xz.com.ar

Onto corre en `onto_web`, publicada en el puerto **8020** del host. El Caddy compartido
(`gateway_caddy`) ya enruta los demás sitios por `host.docker.internal:<puerto>`, así que solo
falta agregar este bloque.

**No modificar el Caddyfile desde este proyecto.** Lo aplica el responsable del gateway.

## Bloque a agregar

```
onto.xz.com.ar {
    tls admin@xz.com.ar

    reverse_proxy host.docker.internal:8020 {
        header_up X-Real-IP {header.CF-Connecting-IP}
        header_up X-Forwarded-For {header.CF-Connecting-IP}
    }
}
```

## Dos advertencias

1. **No importar `security_and_geoblock`.** Ese snippet responde 403 a `AR|CL|UY|BR|PY|BO|PE|EC|CO|VE`;
   bloquearía al público argentino, que es el objetivo del producto.
2. **No agregar `encode` ni `file_server`**: la app ya sirve estáticos con cache headers desde
   WhiteNoise. Un `file_server` en el medio solo genera 404.

## Aplicar

```bash
cp /home/ubuntu/gateway/Caddyfile /home/ubuntu/gateway/Caddyfile.bak-$(date +%F-%H%M)
# pegar el bloque al final
docker exec gateway_caddy caddy validate --config /etc/caddy/Caddyfile
docker exec gateway_caddy caddy reload --config /etc/caddy/Caddyfile
```

Si `validate` falla, el Caddyfile anterior sigue activo: corregir y repetir, sin reiniciar.

## Por qué ahora devuelve 525

`onto.xz.com.ar` ya resuelve a Cloudflare (nube naranja) y el modo SSL está en Full (strict).
Cloudflare llega al origen y el Caddy no tiene certificado para ese hostname todavía, así que el
handshake falla. Al agregar el bloque, Caddy pide el certificado de Let's Encrypt por HTTP-01
(usa el puerto 80, que ya está publicado) y el 525 desaparece en menos de un minuto.

## Verificación

```bash
curl -I https://onto.xz.com.ar                      # 200
curl -s https://onto.xz.com.ar/ | grep canonical    # https://onto.xz.com.ar/
curl -s -o /dev/null -w "%{http_code}\n" https://onto.xz.com.ar/ingresar/   # 200
```

Desde adentro del servidor, sin pasar por Cloudflare:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "Host: onto.xz.com.ar" -H "X-Forwarded-Proto: https" http://127.0.0.1:8020/
```

## Revertir

```bash
cp /home/ubuntu/gateway/Caddyfile.bak-<fecha> /home/ubuntu/gateway/Caddyfile
docker exec gateway_caddy caddy reload --config /etc/caddy/Caddyfile
```
