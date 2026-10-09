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

### Requirement: Origen, versión y vencimiento en el listado
`GET /api/v1/admin/signature-requests` SHALL incluir por ítem `origin` (`{"kind": "individual"}` o `{"kind": "batch", "batch_id": …, "label": "#xxxxxxxx"}` con los primeros 8 caracteres del id del lote) y `document.signature_deadline`. SHALL ordenar las filas de un mismo lote de forma contigua, agrupando por la fecha del lote y luego de la solicitud, y SHALL aceptar el filtro `origin` (`individual` o `batch`) y un filtro de búsqueda `q` por nombre o id externo del documento, o por firmante.

#### Scenario: Filas de un lote juntas
- **WHEN** hay un lote de 3 solicitudes y una individual intercalada en el tiempo
- **THEN** las 3 del lote aparecen consecutivas en el resultado

#### Scenario: Filtro por origen
- **WHEN** se pide `origin=batch`
- **THEN** solo se devuelven solicitudes que pertenecen a un lote

#### Scenario: Búsqueda
- **WHEN** se pide `q=Providencia`
- **THEN** se devuelven las solicitudes de documentos cuyo nombre o id externo contiene el texto, o cuyo firmante coincide

### Requirement: Línea de tiempo de la custodia
`GET /api/v1/admin/documents/{id}/custody` SHALL incluir `timeline`: una lista ordenada por hora de entradas `{at, actor, title, detail, kind}` construida a partir de los eventos de auditoría y de las entregas de webhook del documento, con títulos en español (solicitud creada, método elegido, desafío preparado, certificado rechazado, firma incrustada y nueva versión registrada, firma fallida, sello de tiempo no disponible, webhook entregado o fallido) y `actor` entre el nombre del integrador, el firmante, «Firmadoc Agent» y «Motor Firmadoc». Los datos originales (`events`, `challenges`, `webhook_deliveries`) SHALL conservarse. La línea de tiempo NO SHALL incluir hashes a firmar, cuerpos de webhook ni secretos.

#### Scenario: Historia de una firma
- **WHEN** se consulta un documento firmado con token
- **THEN** la línea de tiempo muestra, en orden, la solicitud creada, el desafío preparado, la firma incrustada con la nueva versión y el webhook entregado, cada uno con su hora y actor

#### Scenario: Certificado rechazado
- **WHEN** hubo un rechazo del certificado
- **THEN** aparece una entrada «Certificado rechazado» con el motivo y sin pedido de PIN posterior

### Requirement: Detalle técnico y versiones con descarga
La custodia SHALL incluir `technical` (por la última solicitud firmada: ID de transacción = id de la solicitud, proveedor, nivel de firma, certificado con sujeto, emisor y serie, firmante, hash del documento original y hash del documento firmado vigente) y, por versión, el nombre de archivo sugerido. `GET /api/v1/admin/documents/{id}/versions/{n}/download` SHALL devolver el PDF de esa versión con el token de administración, con `Cache-Control: no-store`, y `404` si no existe. El detalle NO SHALL incluir la IP de origen, porque el sistema no la registra.

#### Scenario: Datos técnicos
- **WHEN** se consulta un documento con una firma completada
- **THEN** `technical` trae el proveedor, el nivel de firma, el certificado y emisor, y los hashes original y firmado

#### Scenario: Descargar una versión
- **WHEN** se pide la versión 1 de un documento con dos versiones
- **THEN** se obtiene el PDF original sin firma y la versión 2 conserva su firma

#### Scenario: Versión inexistente o sin credenciales
- **WHEN** la versión no existe o falta el token de administración
- **THEN** responde `404` o `401`
