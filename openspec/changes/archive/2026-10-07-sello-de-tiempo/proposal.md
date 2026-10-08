## Why

Una firma digital sin sello de tiempo prueba quién firmó, pero no **cuándo** con una fecha en la que se pueda confiar: la hora de la firma la declara el propio firmante (o el servidor). El sello de una autoridad de sellado de tiempo (TSA, RFC 3161) lo resuelve y es la base de las firmas que duran más que el certificado (también habilita, más adelante, validación a largo plazo). Además cierra una limitación anotada en la rotación del certificado propio: tras un compromiso de clave no se distingue una firma antigua de una forjada porque no hay una fecha confiable.

Backlog: FIRDOC-7 (HU7, sello de tiempo).

## What Changes

- **Sellado en `complete`** (`timestamping`): con `FIRMADOC_TSA_URL` configurada, se pide a la TSA el sello de la firma y se incrusta como atributo no firmado de la firma CMS: PAdES **B-T**. `DocumentVersion.signature_level` queda en `B-T` (sin sello, `B-B`). El bloque `document` y el webhook ya exponen el nivel.
- **TSA no disponible**: política configurable. Por defecto (`FIRMADOC_TSA_REQUIRED=false`) la firma se completa en `B-B` y se registra `timestamp_unavailable`; con `true` responde `503` sin consumir el desafío, de modo que `complete` se puede reintentar sin pedir otra firma (sin otro PIN con el token).
- **Auditoría**: el evento `signed` registra el nivel y el estado del sello (`embedded`, `absent` o `unavailable`).
- **Verificación** (`document-verification`): `verify` informa por firma si hay sello, su fecha y si es íntegro, válido y de confianza; una firma con un sello no confiable deja de ser `ok`.
- **Orden de `complete`**: el PDF firmado (y su sello) se arma **antes** de consumir el desafío, para que un fallo de la TSA no gaste la firma. La concurrencia sigue protegida: el consumo atómico decide quién gana.

## Capabilities

### New Capabilities

- `timestamping`: configuración de la TSA, sellado B-T y política ante fallos.

### Modified Capabilities

- `signature-requests`: "Completar la firma" incluye el sello y sus escenarios.
- `local-signing-provider`: el nivel es B-B o B-T.
- `document-verification`: verificación del sello de tiempo.

## Impact

- Servidor: `timestamping.py`, `pdf_engine.py` (parámetro del sellador y verificación del sello), `services/signature_flow.py` (orden y política), `errors.py` (503), `config.py`, `services/documents.py` y esquemas. Sin migración (`B-T` ya existe en el enum).
- Variables de entorno nuevas: `FIRMADOC_TSA_URL`, `FIRMADOC_TSA_TIMEOUT_SECONDS`, `FIRMADOC_TSA_REQUIRED`.
- Documentación: `docs/timestamping.md`.

## Fuera de alcance

- **B-LT / B-LTA** (datos de revocación y sellos de archivo en el DSS): requiere consultar revocación de toda la cadena al firmar y un mantenimiento periódico del sello; queda como evolución.
- Autenticación contra TSA con credenciales y sellos con política OID específica.
- Elegir la TSA de la institución (decisión de despliegue): se documenta cómo agregar su raíz como ancla desde el panel de administración.
