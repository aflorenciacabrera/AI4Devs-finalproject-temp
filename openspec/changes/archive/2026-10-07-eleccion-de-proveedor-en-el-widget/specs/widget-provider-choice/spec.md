## ADDED Requirements

### Requirement: Pantalla de elección del método
Cuando la solicitud está `pending` y tiene más de un método disponible, el widget SHALL abrir en una pantalla "¿Cómo querés firmar?" que lista cada método con su nombre y una descripción (firma digital con token, firma electrónica de demostración, firma con servicio remoto), SHALL permitir elegir uno y cancelar, y SHALL no tocar la red local ni consultar al agente hasta que se elija el token.

#### Scenario: Varios métodos
- **WHEN** el contexto trae `allowed_providers` con dos o más métodos y estado `pending`
- **THEN** se muestra la elección y no se consulta al agente

#### Scenario: Un solo método
- **WHEN** hay un único método disponible
- **THEN** se salta la elección y se sigue el flujo de ese método, como hasta ahora

#### Scenario: Elegir token
- **WHEN** la persona elige el método con token
- **THEN** se confirma la elección en el servidor y recién entonces se detecta el agente

#### Scenario: Error al elegir
- **WHEN** el servidor rechaza la elección
- **THEN** se muestra un mensaje claro y se puede volver a intentar o cancelar

### Requirement: Volver a elegir otro método
Mientras no se haya preparado la firma, las pantallas de espera o error del widget (agente no encontrado, problema del agente, elegir certificado, certificado rechazado, confirmar firma de demostración y confirmar firma remota) SHALL ofrecer "Elegir otro método" cuando la solicitud tiene más de un método disponible, y ese botón SHALL volver a la pantalla de elección.

#### Scenario: Agente no encontrado
- **WHEN** no se detecta el agente y hay otro método disponible
- **THEN** la pantalla ofrece "Elegir otro método"

#### Scenario: Un solo método
- **WHEN** la solicitud solo permite un método
- **THEN** no se muestra "Elegir otro método"

#### Scenario: Firma en curso
- **WHEN** se está esperando el PIN, completando la firma o esperando al servicio remoto
- **THEN** no se ofrece cambiar de método

### Requirement: Firma remota desde el widget
Con el proveedor `firmar`, el widget SHALL mostrar una pantalla de confirmación, enviar el documento al servicio con `prepare`, mostrar el enlace "Continuar en el servicio de firma" (`target="_blank"` con `rel="noopener noreferrer"`, nunca abierto automáticamente) y consultar el estado de la solicitud periódicamente hasta que sea `signed` o `failed`, mostrando entonces la firma completada o el error y notificando al sistema anfitrión como en los demás métodos.

#### Scenario: Firma remota exitosa
- **WHEN** el servicio informa la firma y la solicitud pasa a `signed`
- **THEN** el widget muestra la firma completada y notifica `signed` al anfitrión

#### Scenario: Rechazo del servicio
- **WHEN** la solicitud pasa a `failed`
- **THEN** el widget muestra el error y notifica `failed` al anfitrión

#### Scenario: Servicio no disponible
- **WHEN** `prepare` responde `503`
- **THEN** se muestra que el servicio remoto no está disponible y se puede reintentar, elegir otro método o cancelar

#### Scenario: Recarga con la firma remota en curso
- **WHEN** se abre el widget con una solicitud `firmar` en `signing`
- **THEN** se muestra la espera sin enlace y se sigue consultando el estado

#### Scenario: Sondeo acotado
- **WHEN** se sale de la pantalla de espera
- **THEN** se deja de consultar el estado
