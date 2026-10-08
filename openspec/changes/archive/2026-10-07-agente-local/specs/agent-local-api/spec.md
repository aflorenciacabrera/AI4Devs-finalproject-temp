## ADDED Requirements

### Requirement: Escucha solo en la interfaz local
El agente SHALL escuchar únicamente en `127.0.0.1` y no SHALL aceptar conexiones por ninguna otra interfaz.

#### Scenario: Interfaz de escucha
- **WHEN** el agente está en ejecución
- **THEN** su socket está enlazado a `127.0.0.1` y no a `0.0.0.0` ni a otra dirección

### Requirement: Solo dos operaciones
El agente SHALL exponer únicamente `GET /certificates` y `POST /sign` (más las preflight `OPTIONS` de esas rutas); cualquier otra ruta o método SHALL responder `404` o `405` sin ejecutar nada.

#### Scenario: Ruta desconocida
- **WHEN** se invoca cualquier otra ruta, por ejemplo `/admin`
- **THEN** la respuesta es `404`

#### Scenario: Método no permitido
- **WHEN** se invoca `POST /certificates` o `GET /sign`
- **THEN** la respuesta es `405`

### Requirement: Lista de orígenes permitidos
Toda solicitud a `GET /certificates` y `POST /sign` SHALL llevar una cabecera `Origin` que coincida exactamente (esquema, host y puerto, sin comodines) con uno de los orígenes de la configuración; en caso contrario SHALL responder `403` con código `origin_not_allowed` sin tocar el token ni mostrar ningún diálogo.

#### Scenario: Origen permitido
- **WHEN** llega un pedido con `Origin: https://firmadoc.example.org` y ese origen está configurado
- **THEN** el pedido se procesa y la respuesta incluye `Access-Control-Allow-Origin` con ese mismo origen

#### Scenario: Origen no permitido
- **WHEN** llega un pedido con un origen que no está en la lista
- **THEN** la respuesta es `403` con `code: "origin_not_allowed"` y no incluye `Access-Control-Allow-Origin`

#### Scenario: Pedido sin Origin
- **WHEN** llega un pedido sin cabecera `Origin` (por ejemplo, desde `curl`)
- **THEN** la respuesta es `403` con `code: "origin_not_allowed"`

#### Scenario: Lista vacía
- **WHEN** la configuración no tiene ningún origen permitido
- **THEN** todos los pedidos se rechazan con `origin_not_allowed`

### Requirement: Validación de Host
El agente SHALL rechazar con `403` y código `host_not_allowed` todo pedido cuya cabecera `Host` no sea `127.0.0.1:{puerto}` ni `localhost:{puerto}`, para impedir ataques de DNS rebinding.

#### Scenario: Host de otro dominio
- **WHEN** el pedido llega con `Host: evil.example.org:47123`
- **THEN** la respuesta es `403` con `code: "host_not_allowed"`

### Requirement: Preflight CORS y acceso a red privada
El agente SHALL responder a `OPTIONS` de sus dos rutas, para orígenes permitidos, con `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers: Content-Type` y, cuando el navegador lo solicita con `Access-Control-Request-Private-Network: true`, con `Access-Control-Allow-Private-Network: true`.

#### Scenario: Preflight de red privada
- **WHEN** Chrome envía `OPTIONS /sign` con `Access-Control-Request-Private-Network: true` desde un origen permitido
- **THEN** la respuesta es `204` e incluye `Access-Control-Allow-Private-Network: true`

#### Scenario: Preflight de origen no permitido
- **WHEN** la preflight llega desde un origen no permitido
- **THEN** la respuesta es `403` sin cabeceras CORS

### Requirement: Formato de los pedidos y límites
`POST /sign` SHALL exigir `Content-Type: application/json`, SHALL rechazar cuerpos mayores a 1 MiB con `413` y SHALL rechazar JSON malformado o campos faltantes con `400` y código `invalid_request`.

#### Scenario: Cuerpo inválido
- **WHEN** el cuerpo no es JSON o no trae `certificate_id` e `items`
- **THEN** la respuesta es `400` con `code: "invalid_request"`

#### Scenario: Demasiados elementos
- **WHEN** `items` tiene más de 100 elementos
- **THEN** la respuesta es `413` con `code: "too_many_items"`

### Requirement: Una firma a la vez
El agente SHALL atender un solo `POST /sign` simultáneamente; un segundo pedido mientras hay un diálogo abierto SHALL responder `429` con código `busy`.

#### Scenario: Pedido concurrente
- **WHEN** llega un segundo `POST /sign` mientras el primero espera la confirmación del usuario
- **THEN** la respuesta al segundo es `429` con `code: "busy"` y el primero no se ve afectado

### Requirement: Errores con código estable
Todas las respuestas de error SHALL tener cuerpo JSON `{"code", "detail"}` con un `code` estable que el widget pueda interpretar, y SHALL llevar la cabecera `X-Firmadoc-Agent` con la versión.

#### Scenario: Cuerpo de error
- **WHEN** un pedido es rechazado por cualquier motivo
- **THEN** el cuerpo contiene `code` y `detail` y la respuesta incluye `X-Firmadoc-Agent`
