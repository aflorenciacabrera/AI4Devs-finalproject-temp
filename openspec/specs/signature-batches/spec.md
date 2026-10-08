# signature-batches Specification

## Purpose
TBD - created by archiving change firma-en-lote. Update Purpose after archive.

## Requirements

### Requirement: Crear un lote
`POST /api/v1/signature-batches` SHALL crear un `SignatureBatch` y una `SignatureRequest` por documento, con un firmante, un proveedor y un `callback_url` opcional comunes, y SHALL ser atómico: si cualquier documento es inválido, no se crea nada. SHALL exigir entre 1 y `max_batch_size` documentos y SHALL rechazar con `401` una API key inválida o ausente.

#### Scenario: Lote válido
- **WHEN** se envían tres documentos PDF válidos con un firmante y el proveedor `local`
- **THEN** responde `201` con el id del lote, estado `pending` y las tres solicitudes con su `document_id`

#### Scenario: Un documento inválido
- **WHEN** uno de los documentos no es un PDF válido
- **THEN** responde `422` y no se crea ningún lote, documento ni solicitud

#### Scenario: Cantidad fuera de rango
- **WHEN** el lote no tiene documentos o supera el máximo configurado
- **THEN** responde `422`

#### Scenario: Documento existente
- **WHEN** un elemento usa un `document_id` ya conocido del mismo integrador
- **THEN** la solicitud opera sobre ese documento sin reenviar el binario

### Requirement: Preparar un lote
`POST /api/v1/signature-batches/{id}/prepare` SHALL preparar cada solicitud del lote con el mismo certificado y SHALL devolver un desafío por documento, cada uno de un solo uso y atado a la misma sesión.

#### Scenario: Preparación
- **WHEN** se prepara un lote de tres documentos con un certificado válido
- **THEN** responde `200` con tres desafíos, uno por solicitud, y las solicitudes pasan a `signing`

#### Scenario: Certificado rechazado
- **WHEN** el certificado no es de confianza, está vencido, revocado o su CUIL no coincide
- **THEN** responde con el mismo error que `prepare` de una solicitud y ninguna solicitud cambia de estado

### Requirement: Completar un lote
`POST /api/v1/signature-batches/{id}/complete` SHALL completar cada solicitud con su firma, creando una `DocumentVersion` firmada por documento exitoso, y SHALL informar el resultado por documento sin que el fallo de uno impida a los demás.

#### Scenario: Todo firmado
- **WHEN** se envían las firmas válidas de todos los documentos
- **THEN** cada documento tiene una nueva versión vigente, el lote queda `completed` y la respuesta lista las versiones

#### Scenario: Fallo parcial
- **WHEN** una firma no verifica contra su hash y las demás sí
- **THEN** esa solicitud queda `failed`, las otras `signed` y el lote `partial_failure`, y la respuesta indica el código de error de la fallida

#### Scenario: Firma faltante
- **WHEN** para un documento no se envía firma
- **THEN** esa solicitud no cambia, el resultado indica la falta y las demás se completan

#### Scenario: Lote ya completado
- **WHEN** se completa un lote cuyas solicitudes ya están firmadas
- **THEN** responde `409` y no se crean versiones nuevas

#### Scenario: Lote sin preparar
- **WHEN** el lote no tiene solicitudes en `signing`
- **THEN** responde `409`

### Requirement: Consultar un lote
`GET /api/v1/signature-batches/{id}` SHALL devolver el estado del lote y el de cada solicitud (documento, estado, versión resultante), solo para el integrador dueño del lote.

#### Scenario: Consulta
- **WHEN** el integrador consulta su lote
- **THEN** recibe el estado agregado y el detalle por solicitud

#### Scenario: Lote ajeno
- **WHEN** otro integrador consulta, prepara o completa ese lote
- **THEN** responde `404`

### Requirement: Estado del lote
El estado de un lote SHALL derivarse de sus solicitudes: alguna `signed`: todas `signed` → `completed`, si no `partial_failure`; ninguna `signed`: todas `failed` → `failed`, alguna `signing` → `signing`, en otro caso `pending`. Al llegar a `completed`, `failed` o `partial_failure` SHALL registrarse `completed_at`.

#### Scenario: Derivación
- **WHEN** las solicitudes están `signed`, `failed` y `signed`
- **THEN** el lote es `partial_failure`

### Requirement: Auditoría y webhooks del lote
Cada operación del lote SHALL registrar un evento sobre `audit_event.batch_id` (`batch_created`, `batch_prepared`, `batch_completed`), y cada solicitud del lote SHALL conservar sus propios eventos y, si hay `callback_url`, su propio webhook.

#### Scenario: Eventos
- **WHEN** se crea, prepara y completa un lote
- **THEN** existen los tres eventos del lote y cada solicitud tiene sus eventos `created`, `prepared` y `signed`

#### Scenario: Webhooks por documento
- **WHEN** un lote con `callback_url` se completa con tres firmas
- **THEN** se registran tres entregas de webhook, una por documento

### Requirement: Método elegible por lote
`POST /api/v1/signature-batches` SHALL aceptar `allowed_providers` opcional (los métodos que la persona puede elegir en el widget), persistido en el lote y aplicado a todas sus solicitudes; sin él, solo vale el proveedor del lote. En lotes SHALL aceptarse únicamente `token` y `local`: `firmar` en `allowed_providers` o como proveedor SHALL rechazarse con `422`.

#### Scenario: Métodos permitidos
- **WHEN** se crea un lote con `provider: "token"` y `allowed_providers: ["token", "local"]`
- **THEN** el lote y sus solicitudes ofrecen ambos métodos

#### Scenario: Firma remota en lote
- **WHEN** se crea un lote con `firmar`
- **THEN** responde `422` y no se crea nada

### Requirement: URL de firma del lote
La respuesta de creación del lote SHALL incluir `signing_url` (`/sign/batch/{id}` con el token en el fragmento), igual que las solicitudes individuales.

#### Scenario: URL en la creación
- **WHEN** se crea un lote
- **THEN** la respuesta incluye una `signing_url` que empieza con `{public_base_url}/sign/batch/{id}#t=`
