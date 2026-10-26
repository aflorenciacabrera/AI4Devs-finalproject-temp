## ADDED Requirements

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
