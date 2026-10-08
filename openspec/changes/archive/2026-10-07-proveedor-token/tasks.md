## 1. Configuración y errores

- [x] 1.1 Agregar `trust_dir` (`backend/trust`) y `revocation_mode` (`soft-fail`) a `Settings` y a `.env.example`
- [x] 1.2 Agregar el campo opcional `code` a `DomainError` y devolverlo en el handler (`{detail, code}`); agregar el error `Forbidden` (403)
- [x] 1.3 Crear `backend/trust/` con un README que explique cómo cargar y verificar las anclas; excluir las claves privadas en `.gitignore`

## 2. PKI de prueba y simulador de agente

- [x] 2.1 Crear `tests/pki.py`: raíz, AC intermedia, firmante válido con `serialNumber=CUIL ...`, vencido, aún no vigente, revocado (con CRL firmada), de otra AC, sin CUIL, sin uso de firma y con RSA 1024
- [x] 2.2 Crear `tests/agent_simulator.py` que firma el `DigestInfo` del hash con la clave del certificado, según el contrato
- [x] 2.3 Escribir `docs/agent-contract.md` (certificado en `prepare`, hash, algoritmo, codificación, errores, límites) y verificar que el simulador lo cumple

## 3. Anclas de confianza

- [x] 3.1 Implementar `trust.py`: carga de `.crt`/`.pem` (autofirmados = raíces, resto = intermedios), cache y huella SHA-256
- [x] 3.2 Comando `python -m firmadoc.trust list` con sujeto y huella
- [x] 3.3 Tests: carga con raíz e intermedia, directorio vacío, huellas

## 4. Validación de certificados

- [x] 4.1 Implementar `certificate_validation.py` con `ValidationContext` de pyHanko-certvalidator (cadena, vigencia, revocación según modo, CRLs inyectables para tests)
- [x] 4.2 Verificar uso de clave y tipo/tamaño de clave pública (RSA >= 2048)
- [x] 4.3 Extraer y comparar el CUIL (función aislada) y mapear cada fallo a su `code`
- [x] 4.4 Tests de cada motivo: válido, otra AC, vencido, no vigente, revocado, sin uso de firma, RSA débil, CUIL distinto y sin CUIL
- [x] 4.5 Tests de modos de revocación: `soft-fail` acepta con `unknown`, `hard-fail` rechaza, `off` no consulta

## 5. Proveedor token

- [x] 5.1 Ampliar la interfaz `SignatureProvider.resolve_certificate` con el firmante y adaptar `LocalPAdESProvider`
- [x] 5.2 Implementar `TokenAgentProvider`: validar y registrar el `Certificate` (serie, CUIL, revocación, vínculo con el firmante); `obtain_signature` exige la firma
- [x] 5.3 Habilitar `token` en el registro de proveedores (`firmar` sigue deshabilitado)

## 6. Integración en el flujo

- [x] 6.1 `prepare`: exigir `certificate_pem` para `token`, validar antes de crear el desafío, registrar el evento `rejected` y no cambiar el estado de la solicitud en caso de rechazo
- [x] 6.2 `complete`: revalidar el certificado, verificar la firma con la clave pública, incrustar, validar el PDF resultante contra las anclas y descartar sin crear versión si no valida
- [x] 6.3 `complete` sin firma en una solicitud `token` responde `422` sin consumir el desafío

## 7. Tests de la API

- [x] 7.1 Flujo `token` de punta a punta con el simulador: versión vigente, descargable y PDF validado con pyHanko y con `openssl`
- [x] 7.2 `prepare` rechaza con el código correcto: otra AC, vencido, revocado, CUIL distinto, sin certificado; no se crea desafío y la solicitud no cambia
- [x] 7.3 `complete` rechaza: firma con otra clave, firma de otro hash, certificado revocado entre `prepare` y `complete`; solicitud `failed` y ninguna versión nueva
- [x] 7.4 Documento firmado con `local` y luego con `token`: ambas firmas válidas
- [x] 7.5 `token` aceptado al crear, `firmar` sigue respondiendo `422`
- [x] 7.6 Los eventos de auditoría (`created`, `rejected`, `prepared`, `signed`, `failed`) quedan registrados

## 8. Documentación y cierre

- [x] 8.1 Documentar en `backend/README.md` cómo configurar anclas y el modo de revocación, y cómo probar el flujo con el simulador
- [x] 8.2 Agregar a `openspec/config.yaml` que el agente se implementará en Python (python-pkcs11, tkinter, PyInstaller)
- [x] 8.3 Ejecutar `pytest` y `ruff check` sin errores
