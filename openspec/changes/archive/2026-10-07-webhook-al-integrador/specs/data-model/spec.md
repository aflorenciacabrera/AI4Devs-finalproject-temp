## ADDED Requirements

### Requirement: Datos de las notificaciones al integrador
El esquema SHALL incluir `signature_request.callback_url` (nulo si no hay), `integrating_system.webhook_secret` (nulo si no está configurado) y en `webhook_delivery` el evento, el cuerpo a enviar, la próxima fecha de intento, el último error y el último estado HTTP recibido, mediante una migración reversible que conserve los datos existentes.

#### Scenario: Migración sobre datos existentes
- **WHEN** se aplica la migración sobre una base con solicitudes y documentos
- **THEN** los datos existentes se conservan y las columnas nuevas quedan nulas

#### Scenario: Reversión
- **WHEN** se revierte la migración
- **THEN** las columnas nuevas desaparecen y el esquema vuelve al anterior

#### Scenario: Inmutabilidad intacta
- **WHEN** se aplica la migración
- **THEN** los triggers de `document_version`, `audit_event` y `signing_challenge` siguen vigentes
