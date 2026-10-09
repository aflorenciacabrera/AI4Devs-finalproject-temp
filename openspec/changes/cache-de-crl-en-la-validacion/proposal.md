## Why

Con el token físico, el widget mostró `network_error` aunque el agente firmó bien. La causa está en el servidor: cada validación del certificado real (en `prepare`, en la revalidación de `complete` y una vez por documento en un lote) consulta la revocación por red desde cero. El OCSP de la AC responde 500 y la CRL de firmantes pesa 9 MB (242.334 revocados); se la descarga de nuevo en cada validación y, además, desde los dos puntos de distribución. Medido: de 11 a 41 segundos por validación; un lote de 4 PDF tardó más de dos minutos en prepararse y el widget desistió. Con la CRL ya en memoria la misma validación tarda ~2 segundos. Implementa **FIRDOC-52** (épica FIRDOC-18); HU «Firmar con token USB desde el sistema web» y HU6 «Firma en lote».

## What Changes

- Caché en memoria, compartida por todo el proceso del servidor, de las CRL obtenidas por red durante una validación. Las siguientes validaciones las reciben como CRL locales mientras estén vigentes (`next_update`); al vencer se descartan y se vuelve a consultar la red. Las CRL repetidas (misma lista desde dos puntos de distribución) se guardan una sola vez.
- Las CRL cargadas desde `FIRMADOC_CRL_DIR` siguen funcionando igual y tienen prioridad; la caché solo suma lo descargado.
- Documentación: `docs/demo.md` y `docs/real-mode.md` explican que la primera validación de un certificado de una AC puede tardar lo que tarde descargar su CRL y que las siguientes usan la copia en memoria.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `certificate-validation`: nuevo requisito «Reutilización de las CRL descargadas» (caché por proceso con vigencia por `next_update`).

## Impact

- `backend/src/firmadoc/certificate_validation.py`: `CrlCache` y su uso en `CertificateChecker` (`_context`/`_run`).
- `tests/test_certificate_validation.py`: pruebas de la caché sin red (una validación alimenta la caché, otra la aprovecha; vencimiento; sin duplicados).
- `docs/demo.md`, `docs/real-mode.md`.
- Sin cambios en el agente ni en la API. El tiempo de espera del widget para `prepare`/`complete` se está ajustando en otra tarea en paralelo (cambios sin commitear en `widget/src/api/serverClient.ts`); este change no toca el widget.

## Fuera de alcance

- Persistir las CRL en disco entre reinicios (se puede hacer con `FIRMADOC_CRL_DIR` a mano).
- Memorizar el resultado de la validación de un certificado entre `prepare` y `complete`: la revalidación al completar sigue siendo completa, solo que ya no descarga la CRL.
- Cambiar el tiempo de espera del widget (en curso en paralelo).
