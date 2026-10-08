## MODIFIED Requirements

### Requirement: Completar la firma
`POST /api/v1/signature-requests/{id}/complete` SHALL verificar que cada firma corresponde a un desafío vigente, incrustar la firma PAdES como actualización incremental, crear la nueva `DocumentVersion` `signed`, actualizar `Document.current_version_id` y `signing_status`, registrar la notificación al integrador cuando hay `callback_url`, incluir un sello de tiempo de una TSA (nivel PAdES B-T) cuando hay una TSA configurada y registrar en el evento `signed` el nivel alcanzado y el estado del sello, y responder `200` con el bloque `document`.

#### Scenario: Firma completada
- **WHEN** se completa una solicitud con un desafío vigente y una firma válida
- **THEN** la solicitud pasa a `signed`, se crea una versión con `origin: signed` y `is_active_version: true`, la versión anterior no se modifica, y la respuesta incluye `download_url` y `signed_document_base64`

#### Scenario: Desafío vencido
- **WHEN** el desafío superó su `expires_at`
- **THEN** la respuesta es `409` y no se crea ninguna versión

#### Scenario: Desafío ya usado
- **WHEN** se intenta completar con un desafío con `consumed_at` establecido
- **THEN** la respuesta es `409`

#### Scenario: Desafío de otra sesión
- **WHEN** el desafío fue preparado para otra sesión de firmante
- **THEN** la respuesta es `409`

#### Scenario: Firma que no verifica
- **WHEN** la firma enviada no verifica contra el hash preparado
- **THEN** la respuesta es `422`, la solicitud pasa a `failed` y se registra el evento `failed`

#### Scenario: Notificación al completar
- **WHEN** la solicitud tiene `callback_url` y se completa la firma
- **THEN** queda registrada una entrega `pending` del evento `signature.signed`

#### Scenario: Con TSA configurada
- **WHEN** hay una TSA configurada y responde
- **THEN** la firma incluye el sello de tiempo, la versión queda con nivel `B-T` y el evento `signed` registra `timestamp: embedded`

#### Scenario: Sin TSA configurada
- **WHEN** no hay TSA configurada
- **THEN** la firma se completa con nivel `B-B` y el evento `signed` registra `timestamp: absent`

#### Scenario: TSA caída y sello no obligatorio
- **WHEN** hay una TSA configurada, no responde y el sello no es obligatorio
- **THEN** la firma se completa con nivel `B-B`, el evento `signed` registra `timestamp: unavailable` con el motivo y se registra el evento `timestamp_unavailable`

#### Scenario: TSA caída y sello obligatorio
- **WHEN** hay una TSA configurada, no responde y el sello es obligatorio
- **THEN** la respuesta es `503` con `code: timestamp_unavailable`, la solicitud sigue en `signing`, el desafío no se consume y se puede reintentar `complete`

