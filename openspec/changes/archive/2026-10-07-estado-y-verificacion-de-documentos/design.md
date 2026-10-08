## Context

`Document.signing_status` pasa a `signed` al completar una firma, pero no hay forma de marcar un documento pendiente ni de fijar un plazo. Las versiones son inmutables y cada firma queda en una `DocumentVersion` `signed` ligada a su `SignatureRequest`. Falta exponer eso y permitir una verificación independiente del estado guardado en la base.

## Goals / Non-Goals

**Goals:** que el integrador gestione el estado y el plazo, vea los firmantes y verifique un PDF; que la verificación no dependa de la base (solo el PDF y las anclas) salvo para el hash registrado.

**Non-Goals:** política de vencimiento, revocación en la verificación, sellos de tiempo, listados (ver proposal).

## Decisions

1. **Transiciones manuales acotadas.** El integrador solo puede fijar `draft` o `pending_signature`; `signed` lo establece únicamente el flujo de firma (`422` si se intenta). Desde `signed` se permite volver a `pending_signature` (otra ronda de firmantes) pero no a `draft`: un documento firmado no vuelve a ser borrador. Alternativa descartada: permitir cualquier transición (se podría ocultar que un documento ya tiene firmas).
2. **El plazo es informativo.** `signature_deadline` exige zona horaria (un instante sin zona es ambiguo) y debe ser futuro al fijarlo; `null` lo borra. `deadline_passed` se calcula al consultar. No se bloquea la firma al vencer porque el comportamiento no está acordado; queda explícito en la propuesta y en la documentación.
3. **Verificar es releer, no confiar.** `verify` lee el PDF de la versión vigente desde el almacenamiento y (a) recalcula SHA-256 y lo compara con `document_hash` (detecta alteración del binario guardado), (b) valida cada firma incrustada con pyHanko contra las anclas. Así detecta lo que la base no puede: un binario modificado fuera de Firmadoc.
4. **Anclas de verificación**: las de `FIRMADOC_TRUST_DIR` (raíces e intermedias) y, si existe, el certificado del proveedor `local` (autofirmado; sin él las firmas de demostración nunca serían "de confianza"). Cada firma indica `trusted`; una firma con certificado desconocido no invalida la integridad pero sí el resultado global.
5. **Resultado global estricto**: `valid` es verdadero solo si el hash coincide, hay al menos una firma y **todas** son íntegras, válidas, de confianza y sin modificaciones posteriores no permitidas (las firmas anteriores admiten únicamente la actualización incremental de otras firmas). Se informa también el detalle por firma, para que el integrador decida con matices.
6. **Los firmantes salen de la base, la verificación del PDF.** `GET /signatures` lee `DocumentVersion` firmadas → solicitud → firmante y certificado: es el registro de Firmadoc. `verify` es la comprobación criptográfica. Se mantienen separados para que una discrepancia sea visible.
7. **Sin auditoría de la verificación**: `audit_event` exige una solicitud o un lote y verificar no modifica nada; se evita ruido y escritura en una operación de lectura.

## Risks / Trade-offs

- Verificar sin consultar revocación puede dar `valid` para un certificado revocado después de firmar; es el comportamiento esperado de una firma ya emitida (la revocación posterior no invalida lo firmado antes) y queda documentado.
- Verificar un PDF grande con muchas firmas cuesta CPU; la ruta es síncrona y está acotada por el tamaño máximo de documento.
