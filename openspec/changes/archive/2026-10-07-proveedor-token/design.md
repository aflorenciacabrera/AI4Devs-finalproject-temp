## Context

Con el flujo `local` archivado, el proveedor `token` reutiliza exactamente `create` / `prepare` / `complete`. Lo que cambia es **quién tiene la clave** (el token del usuario, accesible solo desde su PC) y que el certificado es de un tercero, por lo que hay que **validarlo**. Este change es solo servidor; el agente se construye después contra el contrato que aquí se fija. Los certificados reales de la AC licenciada y el token físico no están disponibles todavía, así que todo se verifica con una PKI de prueba generada en los tests.

## Goals / Non-Goals

**Goals:**
- Validación de certificados de terceros con motivos de rechazo estables, informada antes del PIN.
- Flujo `token` completo y verificable sin hardware mediante un simulador de agente que respeta el contrato.
- Contrato con el agente documentado, para que construirlo sea mecánico.

**Non-Goals:**
- El agente (PKCS#11, diálogo, instalador), sello de tiempo, panel de anclas, lotes, ECDSA.

## Decisions

1. **Validación con `pyhanko-certvalidator`** (ya instalado): `ValidationContext(trust_roots, other_certs, revocation_mode, allow_fetching)` y `CertificateValidator.async_validate_usage`. Alternativa descartada: validar la cadena a mano con `cryptography`, que no cubre revocación ni restricciones de la ruta.
2. **Anclas desde disco** (`FIRMADOC_TRUST_DIR`, por defecto `backend/trust/`): los `.crt`/`.pem` autofirmados son raíces, el resto intermedios. Se cargan una vez por proceso (cache) y se recargan al reiniciar; la gestión desde el panel (FIRDOC-27) queda para después. `python -m firmadoc.trust list` imprime la huella SHA-256 para confirmarla por un canal independiente.
3. **Revocación configurable**: `hard-fail | soft-fail | off`. Por defecto `soft-fail`: una AC cuyo CRL/OCSP esté momentáneamente inaccesible no debe bloquear al organismo, y el estado `unknown` queda registrado en `Certificate.revocation_status` y en la auditoría. Los despliegues exigentes usan `hard-fail`. Para tests offline, el validador acepta CRLs inyectadas (`crls=[...]`) y no usa red (`allow_fetching=False`).
4. **CUIL**: se extrae con regex `CUIL\s*(\d{11})` del `serialNumber` del sujeto; se normaliza el `identifier` del firmante quitando todo lo que no sea dígito. Si falta o no coincide → `403 cuil_mismatch`. El formato real se confirma con un certificado de la AC (pregunta abierta del README); el extractor está aislado en una función para ajustarlo.
5. **Códigos de error**: `DomainError` gana un campo opcional `code`; el handler responde `{"detail", "code"}`. Se mapea la excepción de certvalidator a `expired | revoked | untrusted | invalid` inspeccionando su tipo (`RevokedError`, `ExpiredError`, `PathValidationError`…), nunca el texto.
6. **Firma del token = RSA PKCS#1 v1.5 sobre `DigestInfo(SHA-256, hash)`** (mecanismo PKCS#11 `CKM_RSA_PKCS` con el prefijo DigestInfo armado por el agente). Es exactamente lo que ya verifica `verify_hash_signature` (`Prehashed(SHA256)` + `PKCS1v15`), por lo que el motor PAdES no cambia. Alternativa descartada: `CKM_SHA256_RSA_PKCS`, que exige darle al token los atributos firmados completos y no el hash, rompiendo la decisión de que el agente solo firma hashes.
7. **`TokenAgentProvider`** implementa la misma interfaz: `resolve_certificate(db, pem)` valida y registra el `Certificate` (get-or-create por serie, con `cuil`, `revocation_status` y `signer_id` si coincide); `obtain_signature(hash, supplied)` exige `supplied` (si es `None` lanza `ValueError` → `422`). El proveedor necesita al firmante para el CUIL: se amplía la interfaz con un parámetro `signer` en `resolve_certificate`.
8. **Revalidación al completar**: la validación del certificado se repite con el DER guardado en el estado intermedio (vigencia y revocación pueden haber cambiado). Tras incrustar, se valida el PDF con pyHanko contra las anclas (`validate_pdf_signature`), y si la firma recién creada no valida se descarta sin crear versión.
9. **Rechazo no destructivo en `prepare`**: un certificado inválido no cambia el estado de la solicitud (el usuario puede reintentar con otro certificado) pero deja el evento de auditoría `rejected` con el código.
10. **Simulador de agente** en `tests/agent_simulator.py`: genera la PKI de prueba (raíz, AC intermedia, firmantes con CUIL, vencido, revocado con CRL, de otra AC, RSA 1024) con `cryptography` y firma `DigestInfo` como lo haría el agente; es la referencia ejecutable del contrato.
11. **Estados al fallar `complete`**: firma que no verifica o certificado revocado → solicitud `failed` y desafío sin consumir (el consumo ocurre después de las verificaciones, ya implementado).

## Risks / Trade-offs

- **Formato real del CUIL y cadena de la AC desconocidos:** se validan con certificados reales en cuanto estén; mitigado con la función de extracción aislada y el comando de huellas.
- **`soft-fail` por defecto acepta certificados no verificables en su revocación:** compromiso consciente, visible en auditoría y configurable.
- **Cadena RSA-only:** tokens con ECDSA se rechazan; si el token real es ECDSA habrá que ampliar el verificador.
- **Dependencia de la API de `pyhanko-certvalidator`** para clasificar errores; cubierto por tests de cada motivo.
- **Cargar anclas desde disco exige confianza en quien administra el servidor:** se mitiga con las huellas y, más adelante, la gestión auditada del panel.

## Open Questions

- ¿`soft-fail` o `hard-fail` por defecto en producción? Depende de la disponibilidad de las CRL/OCSP de la AC.
- ¿El token firma `DigestInfo` con `CKM_RSA_PKCS` en todos los modelos usados por el organismo? Se confirma en el change del agente con un token real.
