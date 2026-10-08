## Why

El modo principal de Firmadoc es la firma digital con el token del funcionario, pero hoy el proveedor `token` responde `422` ("no habilitado"). Este change construye la parte de **servidor**: aceptar un certificado público del token, validarlo (cadena de confianza, vigencia, revocación, CUIL), y completar la firma con el hash firmado por el agente. Se hace antes que el agente porque fija el contrato exacto entre ambos y se puede verificar por completo con certificados de prueba, sin hardware (un simulador de agente en los tests firma con una clave de prueba siguiendo el mismo contrato).

El agente local (FIRDOC-21) es un change posterior; su implementación será en Python (python-pkcs11, diálogo tkinter, empaquetado con PyInstaller).

Backlog: FIRDOC-20 (HU2, firma con token), FIRDOC-29 (validación de confianza), FIRDOC-27 (anclas de confianza: solo la carga desde disco; la gestión desde el panel queda fuera).

## What Changes

- **Validación de certificados de terceros** (`certificate-validation`): cadena hasta las anclas de `backend/trust/`, vigencia, uso de clave (firma/no repudio), revocación (CRL/OCSP) y extracción/comparación del CUIL.
- **Proveedor `token`** (`token-provider`): `prepare` recibe `certificate_pem`, lo valida **antes** de pedir el PIN y devuelve el hash; `complete` recibe la firma que produjo el token, la verifica contra el hash y contra la clave pública del certificado, **revalida** el certificado y verifica el PDF resultante contra las anclas de confianza.
- **Contrato con el agente** documentado en `docs/agent-contract.md`: formato del hash, algoritmo de firma (RSA PKCS#1 v1.5 sobre `DigestInfo` SHA-256), codificación y errores.
- `prepare` pasa a devolver errores con código estable (`403` CUIL no coincide; `422` con `code`: `certificate_expired`, `certificate_revoked`, `certificate_untrusted`, `certificate_invalid`).
- Carga de anclas de confianza desde disco y comando `python -m firmadoc.trust list` que muestra la huella SHA-256 de cada una.
- El proveedor `token` queda habilitado en la creación de solicitudes (`firmar` sigue sin estarlo).
- Registro en `Certificate` de los datos públicos del certificado (subject, emisor, serie, CUIL, estado de revocación) y vínculo con el `Signer`.

## Capabilities

### New Capabilities

- `certificate-validation`: validación de certificados X.509 de firmantes contra anclas de confianza, con motivos de rechazo estables.
- `token-provider`: proveedor de firma `token` (firma diferida con clave en el token del usuario) y su contrato con el agente.

### Modified Capabilities

- `signature-requests`: ya no rechaza `provider: token` al crear; `prepare` incorpora los errores de validación del certificado.

## Impact

- Código nuevo: `backend/src/firmadoc/trust.py`, `certificate_validation.py`, `providers/token.py`; cambios en `providers/__init__.py`, `services/signature_flow.py`, `errors.py`, `config.py`.
- Dependencias: ninguna nueva (pyHanko/certvalidator ya instalados).
- Variables de entorno nuevas: `FIRMADOC_TRUST_DIR` (por defecto `backend/trust`), `FIRMADOC_REVOCATION_MODE` (`hard-fail` | `soft-fail` | `off`, por defecto `soft-fail`), `FIRMADOC_REVOCATION_FETCH` (consultar CRL/OCSP por red) y `FIRMADOC_CRL_DIR` (CRLs locales, para entornos sin internet y para los tests).
- Documentación: `docs/agent-contract.md`, sección de `backend/README.md`.
- Sin cambios de esquema.

## Fuera de alcance

- El agente local, PKCS#11, diálogo de confirmación e instalador (change `agente-local`, FIRDOC-21).
- Sello de tiempo / B-LT (FIRDOC-7): las firmas con token quedan en B-B.
- Panel para gestionar anclas y rotar certificados (FIRDOC-27).
- Firma en lote (FIRDOC-22), webhooks (FIRDOC-24), widget (FIRDOC-30), proveedor `firmar`.
- Certificados con claves no RSA (ECDSA): se rechazan con `certificate_invalid` hasta confirmar con el token real.
- Validación con certificados reales de una AC licenciada: requiere cargar las anclas oficiales y un token físico (pendiente de datos del organismo).
