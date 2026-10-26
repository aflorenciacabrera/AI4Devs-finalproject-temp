## Why

Al firmar con token, Firmadoc rechaza con `403 cuil_mismatch` todo certificado cuyo CUIL no coincida con el `identifier` del firmante de la solicitud (o que no traiga CUIL). En la práctica eso obliga a conocer y cargar de antemano el CUIL exacto de quien va a firmar, y hoy bloquea la primera firma con el token físico desde el panel. La usuaria pidió que lo único que se exija para firmar sea el **PIN personal del token**: quien tiene el dispositivo y conoce el PIN firma, y el certificado que firmó queda registrado. Implementa **FIRDOC-50** (épica FIRDOC-18, «Proveedor token y Firmadoc Agent»); afecta a la HU «Firmar con token USB desde el sistema web» del README.

## What Changes

- **BREAKING (comportamiento por defecto):** `prepare` del proveedor `token` deja de cotejar el CUIL del certificado con el del firmante y deja de exigir que el certificado tenga CUIL. La validación del certificado sigue completa (cadena de confianza, vigencia, uso de clave, revocación, algoritmo) y sigue ocurriendo **antes** de pedir el PIN.
- Nueva variable `FIRMADOC_REQUIRE_CUIL_MATCH` (por defecto `false`). Con `true` se recupera el comportamiento anterior (`403 cuil_mismatch`), para integradores que necesiten garantizar que firma exactamente la persona indicada en la solicitud.
- La firma completada sigue registrando el sujeto, el CUIL (si lo tiene) y el emisor del certificado que efectivamente firmó: la trazabilidad de «quién firmó» no depende del cotejo.
- `python -m firmadoc.preflight` emite una **advertencia** (no un error) cuando el modo real corre sin cotejo de CUIL.
- La demo ya no necesita `--cuil` para firmar con un token físico; `--cuil`/`--nombre` quedan como forma de etiquetar al firmante del panel.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `certificate-validation`: «Vinculación de identidad por CUIL» pasa a ser opcional: la extracción del CUIL se mantiene; la comparación con el firmante solo se hace si el integrador la pide (`FIRMADOC_REQUIRE_CUIL_MATCH=true`).
- `token-provider`: «Preparar con el certificado del token» ya no vincula el CUIL con el firmante por defecto; el escenario «CUIL de otra persona» solo aplica con el cotejo activado.
- `pdf-upload-signing`: el escenario «Firmante configurado» deja de exigir que el certificado del token tenga ese CUIL.
- `signature-batches`: el rechazo del lote por «CUIL no coincide» solo aplica con el cotejo activado.
- `real-mode`: el preflight advierte cuando el modo real corre sin cotejo de CUIL.

## Impact

- `backend/src/firmadoc/config.py` (`require_cuil_match`), `providers/token.py` (pasa `expected_cuil` solo si está activado), `preflight.py` (advertencia).
- Tests: `tests/test_token_flow.py`, `tests/test_widget_endpoints.py`, `tests/test_signature_batches.py`, `tests/test_real_mode.py` (o el de preflight) y un test nuevo que cubre ambos valores del interruptor.
- Documentación: `README.md` (flujos a probar y errores de la API), `docs/agent-contract.md` (tabla de códigos), `docs/demo.md`, `docs/real-mode.md`, `.env.example`.
- Sin cambios en el agente ni en el widget: el mensaje de `cuil_mismatch` del widget sigue existiendo para cuando el cotejo está activado.

## Fuera de alcance

- El proveedor remoto `firmar` sigue enviando y cotejando el CUIL: ese servicio lo necesita para derivar la operación a la persona correcta.
- Cambiar qué datos del firmante se piden al crear una solicitud o al cargar un PDF desde el panel.
- Autorizar al firmante por otros medios (por ejemplo, lista de CUIL habilitados).
