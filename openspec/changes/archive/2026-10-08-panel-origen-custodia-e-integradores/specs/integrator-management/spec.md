## ADDED Requirements

### Requirement: Gestión de integradores desde la API de administración
Bajo `/api/v1/admin/integrators` (token de administración) SHALL existir: `GET` (lista con id, nombre, orígenes permitidos, si tiene secreto de webhook, estado `active`/`disabled`, si es interno y fecha de alta), `POST` (crea con nombre y orígenes), `PATCH /{id}` (cambia los orígenes permitidos), `POST /{id}/rotate-webhook-secret`, `POST /{id}/rotate-api-key` y `POST /{id}/disable` y `/enable`. Las respuestas NO SHALL incluir el hash de la API key. La API key y el secreto de webhook en claro SHALL devolverse **solo** en la respuesta de la creación y de su rotación. De la API key solo se guarda el hash; el secreto de webhook se guarda (hace falta para firmar las notificaciones) pero ningún listado ni evento lo expone.

#### Scenario: Crear un integrador
- **WHEN** se crea un integrador con nombre y orígenes válidos
- **THEN** responde `201` con la API key y el secreto de webhook en claro, y un listado posterior no los incluye

#### Scenario: Validaciones
- **WHEN** el nombre ya existe, es el reservado del panel o un origen no tiene el formato `https://host[:puerto]`
- **THEN** responde `422` y no se crea ni cambia nada

#### Scenario: Rotar la API key
- **WHEN** se rota la API key de un integrador
- **THEN** se devuelve la nueva en claro una sola vez y la anterior deja de autenticar

### Requirement: Integrador deshabilitado
Un integrador `disabled` NO SHALL poder autenticarse con su API key (`401` con un mensaje que no revele la causa) ni crear solicitudes, y sus enlaces de widget ya emitidos SHALL seguir funcionando hasta vencer solo para terminar firmas en curso. Habilitarlo SHALL restablecer el acceso.

#### Scenario: API key de un integrador deshabilitado
- **WHEN** se deshabilita un integrador y este usa su API key
- **THEN** responde `401`

#### Scenario: Volver a habilitar
- **WHEN** se habilita de nuevo
- **THEN** su API key vuelve a autenticar

### Requirement: Auditoría y protección del sistema interno
Cada acción de creación, cambio de orígenes, rotación, deshabilitación y habilitación SHALL registrar un evento en `admin_event` con el integrador y el detalle (sin secretos ni claves). El sistema interno «Firmadoc (panel)» SHALL aparecer como interno y rechazar con `409` cualquier modificación, rotación o deshabilitación.

#### Scenario: Evento sin secretos
- **WHEN** se rota un secreto de webhook
- **THEN** existe un evento con el integrador y la acción, y el valor del secreto no figura en el evento

#### Scenario: Sistema interno
- **WHEN** se intenta rotar la API key o deshabilitar «Firmadoc (panel)»
- **THEN** responde `409` y no cambia nada
