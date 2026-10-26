# Webhooks de Firmadoc

Firmadoc avisa al sistema integrador cuando una solicitud de firma termina (`signed`) o falla (`failed`).
Para recibir avisos, enviar `callback_url` al crear la solicitud (`POST /api/v1/signature-requests`).

## Requisitos de la URL

- `https`, sin usuario ni contraseña, de hasta 2000 caracteres.
- El host debe resolver **solo** a direcciones públicas. Se rechazan loopback, redes privadas, link-local
  (incluida `169.254.169.254`), `100.64.0.0/10`, multicast e IPv6 locales o mapeadas a IPv4 privada.
- Se vuelve a comprobar en cada intento de entrega. No se siguen redirecciones y la respuesta nunca se lee.
- Una URL inválida devuelve `422` con `code: invalid_callback_url` y no se crea nada.

Para desarrollo local: `FIRMADOC_WEBHOOK_ALLOW_HTTP=true` y `FIRMADOC_WEBHOOK_ALLOW_PRIVATE_HOSTS=true`.
No usarlos en producción.

## Evento

`POST` con `Content-Type: application/json`. Eventos: `signature.signed` y `signature.failed`.

```json
{"certificate":{"issuer_subject":"…","serial_number":"…","subject":"…"},
 "created_at":"2026-10-07T21:00:00+00:00","delivery_id":"…","event":"signature.signed",
 "document":{"download_url":"https://…/versions/2/download","external_document_id":"EXP-1","id":"…",
             "is_active_version":true,"signature_level":"B-B","signing_status":"signed","version_number":2},
 "signature_request":{"document_id":"…","external_document_id":"EXP-1","id":"…","provider":"local","status":"signed"}}
```

En `signature.failed` no hay `document` ni `certificate`; hay `"error": {"code": "…"}`. El PDF nunca viaja en el
webhook: descargarlo desde `download_url` con la API key.

## Verificar la firma

Cabeceras: `X-Firmadoc-Signature: t=<epoch>,v1=<hex>`, `X-Firmadoc-Event`, `X-Firmadoc-Delivery`.
`v1 = HMAC-SHA256(webhook_secret, "<t>." + cuerpo_crudo)`. Verificar sobre los **bytes crudos** y rechazar si
`t` se aleja más de 5 minutos.

```python
import hashlib, hmac, time

def verify(secret: str, body: bytes, header: str, tolerance: int = 300) -> bool:
    fields = dict(p.split("=", 1) for p in header.split(","))
    t = int(fields["t"])
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return abs(time.time() - t) <= tolerance and hmac.compare_digest(expected, fields["v1"])
```

```js
const crypto = require("crypto");
function verify(secret, rawBody, header, tolerance = 300) {
  const f = Object.fromEntries(header.split(",").map((p) => p.split(/=(.*)/s).slice(0, 2)));
  const expected = crypto.createHmac("sha256", secret).update(`${f.t}.`).update(rawBody).digest("hex");
  const a = Buffer.from(expected), b = Buffer.from(f.v1 ?? "");
  return Math.abs(Date.now() / 1000 - Number(f.t)) <= tolerance && a.length === b.length && crypto.timingSafeEqual(a, b);
}
```

## Entrega, reintentos e idempotencia

- Garantía **al menos una vez**: puede llegar duplicado. Deduplicar por `delivery_id` (es el mismo en todos los
  reintentos, y el cuerpo también es idéntico).
- Se considera entregado con cualquier `2xx`. Otro resultado (o error de red, o tiempo agotado de 5 s) reintenta
  con esperas de 30 s, 2 min, 10 min, 1 h y 6 h; tras el sexto intento queda `failed`.
- Cada resultado final queda en la auditoría (`webhook_delivered` / `webhook_failed`) y los intentos en
  `webhook_delivery`.
- Responder rápido (`2xx`) y procesar después.

## Alta del integrador y rotación del secreto

```
python -m firmadoc.integrators create --name "Gestor documental" --origins https://gestor.example.org
python -m firmadoc.integrators rotate-webhook-secret --name "Gestor documental"
python -m firmadoc.integrators list
```

La API key y el secreto se muestran una sola vez. De la API key solo se guarda el hash; el secreto del webhook se
guarda en claro porque hace falta para firmar (limitación conocida; en producción conviene cifrarlo o usar un
gestor de secretos).
