# Agent Token Signing Specification

## Purpose

Listado de certificados del token y firma de hashes por PKCS#11 con confirmación del usuario, un solo PIN por lote y sin reintentos.

## Requirements

### Requirement: Listado de certificados sin PIN
`GET /certificates` SHALL listar los certificados públicos de usuario presentes en los tokens conectados, sin pedir el PIN, devolviendo para cada uno `id`, `token_label`, `subject`, `issuer`, `serial_number`, `not_before`, `not_after` y `certificate_pem`; SHALL omitir los certificados de AC.

#### Scenario: Token con un certificado
- **WHEN** hay un token conectado con un certificado de usuario
- **THEN** la respuesta es `200` con ese certificado y `agent_version`

#### Scenario: Certificados de AC en el token
- **WHEN** el token también contiene la AC intermedia
- **THEN** la AC no figura en la lista

#### Scenario: Sin token
- **WHEN** no hay ningún token conectado
- **THEN** la respuesta es `404` con `code: "token_not_found"`

#### Scenario: Biblioteca PKCS#11 no disponible
- **WHEN** el módulo PKCS#11 configurado no existe o no carga
- **THEN** la respuesta es `500` con `code: "pkcs11_unavailable"` y el detalle de la causa

### Requirement: Confirmación del usuario antes de firmar
`POST /sign` SHALL mostrar un diálogo con el nombre de cada documento y el sujeto del certificado, y SHALL firmar solamente si el usuario confirma; si cancela o no responde en el tiempo límite SHALL responder `409` con código `user_cancelled` sin haber abierto sesión en el token.

#### Scenario: Usuario cancela
- **WHEN** el usuario cierra el diálogo o pulsa Cancelar
- **THEN** la respuesta es `409` con `code: "user_cancelled"` y no se intentó ningún login

#### Scenario: Tiempo agotado
- **WHEN** el usuario no responde en 120 segundos
- **THEN** el diálogo se cierra y la respuesta es `409` con `code: "user_cancelled"`

#### Scenario: Nombres a mostrar
- **WHEN** el pedido trae tres documentos
- **THEN** el diálogo muestra los tres nombres tal como llegaron en `document_name`

### Requirement: Un solo PIN por lote y nunca reintentar
El agente SHALL pedir el PIN una única vez por pedido, abrir una sola sesión, firmar todos los hashes y cerrarla; si el PIN es incorrecto SHALL responder el error sin reintentar por su cuenta.

#### Scenario: Lote de tres hashes
- **WHEN** el pedido trae tres elementos y el PIN es correcto
- **THEN** el agente pide el PIN una sola vez, firma los tres y devuelve tres firmas

#### Scenario: PIN incorrecto
- **WHEN** el usuario ingresa un PIN incorrecto
- **THEN** la respuesta es `401` con `code: "pin_incorrect"` y el agente realizó exactamente un intento de login

#### Scenario: PIN bloqueado
- **WHEN** el token informa el PIN bloqueado
- **THEN** la respuesta es `423` con `code: "pin_locked"`

#### Scenario: Último intento
- **WHEN** el token indica que queda un único intento
- **THEN** la respuesta de error o el diálogo advierte "último intento antes del bloqueo"

### Requirement: Firma del hash con el mecanismo del contrato
Por cada elemento, el agente SHALL validar que `hash_algorithm` sea `SHA-256` y que `hash_to_sign` decodifique a 32 bytes, y SHALL firmar con `CKM_RSA_PKCS` el `DigestInfo` SHA-256 de ese hash con la clave privada del certificado elegido.

#### Scenario: Firma verificable por el servidor
- **WHEN** el agente firma un hash
- **THEN** la firma devuelta es RSA PKCS#1 v1.5 sobre `DigestInfo || hash` y verifica con la clave pública del certificado

#### Scenario: Algoritmo no soportado
- **WHEN** un elemento declara `hash_algorithm: "SHA-512"` o un hash de longitud distinta de 32 bytes
- **THEN** la respuesta es `400` con `code: "invalid_request"` y no se muestra ningún diálogo

#### Scenario: Certificado inexistente
- **WHEN** `certificate_id` no corresponde a ningún certificado del token
- **THEN** la respuesta es `404` con `code: "certificate_not_found"`

### Requirement: Sin datos sensibles fuera del token
El agente SHALL NOT registrar ni persistir el PIN, SHALL NOT enviar nada a ningún servidor y SHALL mantener el PIN en memoria solo el tiempo necesario para el login.

#### Scenario: Registro de actividad
- **WHEN** se completa una firma con el registro en nivel de detalle máximo
- **THEN** el archivo de registro no contiene el PIN y no contiene las firmas ni los hashes completos

### Requirement: Cierre ordenado de la sesión
El agente SHALL cerrar la sesión del token (logout y cierre) tras firmar, ante un error o ante una cancelación posterior al login, sin dejar el token autenticado.

#### Scenario: Error durante la firma
- **WHEN** falla la firma del segundo de tres hashes
- **THEN** la respuesta es un error, no se devuelve ninguna firma parcial y la sesión queda cerrada
