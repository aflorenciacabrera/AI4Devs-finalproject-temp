## ADDED Requirements

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
