# Registros y observabilidad

Qué registra Firmadoc, cómo seguir una firma concreta y qué no se registra nunca. La auditoría (tabla
`audit_event`, panel «Documentos») sigue siendo la **fuente de verdad** de quién firmó qué; los registros
sirven para investigar por qué algo tardó o falló.

## Qué se registra

Con el servidor en marcha, el logger `firmadoc` escribe en la salida estándar **una línea JSON por evento**
(`backend/src/firmadoc/observability.py`). Hay dos tipos:

**Un registro por pedido HTTP** (`http_request`), al terminar:

```json
{"ts": "2026-11-18T21:32:00.412+00:00", "level": "info", "logger": "firmadoc.http", "event": "http_request",
 "request_id": "5f0c2a7e9b1d4c3fa8e6d2b4c1a09f7e", "method": "POST",
 "route": "/api/v1/widget/requests/{request_id}/complete",
 "path": "/api/v1/widget/requests/b3f1c2e0-.../complete", "status": 200, "duration_ms": 184.3}
```

- `route` es la ruta declarada, igual para todas las solicitudes: es la que se usa para agrupar y medir.
- `/health` se registra en nivel `debug` (no aparece con el nivel por defecto).

**Un registro por evento de auditoría** (`audit.<tipo>`): `created`, `prepared`, `signed`, `failed`,
`rejected`, `timestamp_unavailable` y los de lote (`batch_created`, `batch_prepared`, `batch_completed`):

```json
{"ts": "...", "level": "info", "logger": "firmadoc.events", "event": "audit.signed",
 "request_id": "5f0c2a7e9b1d4c3fa8e6d2b4c1a09f7e", "signature_request_id": "b3f1c2e0-...",
 "signature_level": "B-B"}
```

Lleva identificadores (`signature_request_id`, `batch_id`) y, del detalle, solo `provider`, `code`,
`documents`, `signed`, `errors` y `signature_level`. Si la transacción se deshace, el registro queda y el
evento de auditoría no: ante la duda vale la auditoría.

## El identificador de pedido

Cada pedido recibe un `request_id` que aparece en todos sus registros y vuelve en la cabecera de respuesta
`X-Request-ID`. Un sistema integrador puede mandar el suyo en esa misma cabecera para unir sus registros con
los de Firmadoc; se acepta solo si tiene entre 8 y 64 caracteres de `A-Z a-z 0-9 . _ -` (si no, se genera
uno nuevo: nunca se copia a los registros un texto arbitrario).

Para seguir una firma: buscar por `signature_request_id` (todos sus eventos) o por `request_id` (todo lo que
pasó dentro de un pedido). Por ejemplo, con los registros de la demo en contenedores:

```bash
docker compose logs demo --no-log-prefix | grep '"signature_request_id": "b3f1c2e0'
```

Una firma con token son varios pedidos (`prepare`, la firma en la PC, `complete`): los une el
`signature_request_id`, no el `request_id`.

## Qué NO se registra nunca

- El **PIN** y la clave privada: no llegan al servidor.
- **Tokens, API keys y secretos** (el token del widget viaja en el fragmento de la URL, que el navegador no
  envía; las cabeceras no se registran).
- El **contenido** de los documentos, las firmas y los certificados.
- La **cadena de consulta** de la URL.
- **Datos personales del firmante** (nombre, CUIL, correo): los eventos llevan identificadores, no personas.

Como red de seguridad, si un campo con nombre sensible (`pin`, `token`, `secret`, `api_key`, `cuil`,
`email`, `base64`, `pem`…) llegara a un registro por error, su valor se reemplaza por `[omitido]`.
Las pruebas (`tests/test_observability.py`) firman un documento y comprueban que nada de eso aparece.

## Configuración

| Variable | Valores | Por defecto |
|---|---|---|
| `FIRMADOC_LOG_FORMAT` | `json` (una línea por evento) o `text` (legible, para desarrollo) | `json` |
| `FIRMADOC_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

Los registros de acceso de uvicorn siguen saliendo en su formato; para dejar solo los estructurados,
arrancar uvicorn con `--no-access-log`.

## Qué no hay (todavía)

- **Trazas distribuidas y métricas** (OpenTelemetry): Firmadoc es un solo proceso y con el identificador de
  pedido alcanza para seguir una firma. Sumarlo sería agregar dependencias; queda como decisión futura.
- **Un destino para los registros**: salen por la salida estándar y los junta lo que ejecute el contenedor
  (`docker compose logs`, o el recolector de la plataforma). Cuánto tiempo se guardan lo decide ese destino.
- **Alertas automáticas**: el SLO (`docs/slo/api.md`) se mide a pedido con `python -m firmadoc.slo`.
- El **agente local** tiene su propio registro de actividad en la PC del firmante (`agent/README.md`); no
  comparte el identificador de pedido.
