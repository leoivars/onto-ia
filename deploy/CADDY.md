# Enrutar onto.zx.com.ar por el Caddy compartido

El servidor tiene un único Caddy (`gateway_caddy`) escuchando 80/443 que enruta por hostname a
los puertos altos de cada proyecto. Onto publica su web en `8020`, así que falta una sola cosa:
un bloque en ese Caddyfile.

Archivo: `/home/ubuntu/gateway/Caddyfile` (fuera del espacio `~/onto`).

## Bloque a agregar

```
onto.zx.com.ar {
    tls admin@xz.com.ar

    reverse_proxy host.docker.internal:8020 {
        header_up X-Real-IP {header.CF-Connecting-IP}
        header_up X-Forwarded-For {header.CF-Connecting-IP}
    }
}
```

**No importar `security_and_geoblock`.** Ese snippet responde 403 a los países que matchean
`AR|CL|UY|BR|PY|BO|PE|EC|CO|VE`: bloquearía justamente al público argentino. Los otros sitios lo
usan por decisión propia; Onto no debe.

## Aplicar

```bash
cp /home/ubuntu/gateway/Caddyfile /home/ubuntu/gateway/Caddyfile.bak-$(date +%F)
# editar y agregar el bloque al final
docker exec gateway_caddy caddy validate --config /etc/caddy/Caddyfile
docker exec gateway_caddy caddy reload --config /etc/caddy/Caddyfile
```

`caddy reload` no corta las conexiones existentes de los otros sitios. Si la validación falla, el
Caddyfile actual sigue funcionando y no hay que reiniciar nada.

## Cloudflare

1. DNS → Add record: `A`, name `onto`, content `163.176.237.182`, **Proxied**.
2. SSL/TLS → modo **Full (strict)** (Caddy emite Let's Encrypt por HTTP-01, que funciona detrás
   del proxy naranja).
3. Comprobar: `curl -I https://onto.zx.com.ar` → 200.

## Revertir

```bash
cp /home/ubuntu/gateway/Caddyfile.bak-<fecha> /home/ubuntu/gateway/Caddyfile
docker exec gateway_caddy caddy reload --config /etc/caddy/Caddyfile
```
