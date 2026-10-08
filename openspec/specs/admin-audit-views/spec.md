# admin-audit-views Specification

## Purpose
TBD - created by archiving change panel-de-administracion. Update Purpose after archive.

## Requirements

### Requirement: Historial de solicitudes de firma
`GET /api/v1/admin/signature-requests` SHALL listar las solicitudes de todos los integradores, de la más reciente a la más antigua, con el integrador, el documento (id externo, estado de firma y versión vigente), el firmante, el proveedor, el estado, las fechas y el certificado, y SHALL admitir filtros por integrador, estado, proveedor, firmante y rango de fechas de creación, con paginación (`limit` hasta 200, 50 por defecto, y `offset`) y el `total`.

#### Scenario: Sin filtros
- **WHEN** se lista sin filtros
- **THEN** devuelve la primera página, ordenada por fecha descendente, con el total

#### Scenario: Filtros combinados
- **WHEN** se filtra por integrador, estado `signed` y un rango de fechas
- **THEN** solo aparecen las que cumplen todo

#### Scenario: Filtro por firmante
- **WHEN** se filtra por un CUIL, o por un texto del nombre sin distinguir mayúsculas
- **THEN** aparecen las solicitudes de ese firmante; los comodines `%` y `_` del texto se toman literalmente

#### Scenario: Paginación
- **WHEN** hay más resultados que `limit`
- **THEN** `offset` recorre las páginas y `total` no cambia

#### Scenario: Parámetros inválidos
- **WHEN** `limit` es mayor que 200 o menor que 1, o un estado no existe
- **THEN** responde `422`

### Requirement: Cadena de custodia de un documento
`GET /api/v1/admin/documents/{id}/custody` SHALL devolver todas las versiones del documento (número, origen, nivel, hash, fecha, si es la vigente), sus solicitudes con los eventos de auditoría, los desafíos de firma (id, fechas, si se consumió) y las entregas de webhook (estado, intentos, error), sin devolver el hash a firmar, el cuerpo de los webhooks ni el contenido de ningún PDF.

#### Scenario: Documento con dos firmas
- **WHEN** se consulta la custodia de un documento firmado dos veces
- **THEN** aparecen sus tres versiones con la vigente marcada, sus dos solicitudes con eventos y sus desafíos consumidos

#### Scenario: Sin secretos
- **WHEN** se consulta la custodia
- **THEN** la respuesta no contiene `hash_to_sign` ni cuerpos de webhook

#### Scenario: Documento inexistente
- **WHEN** el id no existe
- **THEN** responde `404`

### Requirement: Entregas de webhook
`GET /api/v1/admin/webhook-deliveries` SHALL listar las entregas con su estado, intentos, último intento, siguiente intento, último error y estado HTTP, con filtro por estado y paginación. `POST /api/v1/admin/webhook-deliveries/{id}/retry` SHALL reencolar una entrega `failed` (estado `pending`, intentos en 0, próximo intento ahora) y registrar un `admin_event` con los intentos previos.

#### Scenario: Reenvío
- **WHEN** se reenvía una entrega `failed`
- **THEN** queda `pending` para el próximo ciclo del trabajador y existe un `admin_event` con los intentos previos

#### Scenario: Entrega no reenviable
- **WHEN** la entrega está `delivered` o `pending`
- **THEN** responde `409` y no cambia

#### Scenario: Inexistente
- **WHEN** el id no existe
- **THEN** responde `404`
