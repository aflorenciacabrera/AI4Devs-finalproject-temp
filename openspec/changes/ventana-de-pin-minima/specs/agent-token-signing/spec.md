## MODIFIED Requirements

### Requirement: Confirmación del usuario antes de firmar
`POST /sign` SHALL mostrar un diálogo que pida el PIN y SHALL firmar solamente si el usuario confirma; si cancela o no responde en el tiempo límite SHALL responder `409` con código `user_cancelled` sin haber abierto sesión en el token. El diálogo SHALL mostrar únicamente el nombre del titular del certificado (CN del sujeto; si no hay CN, el sujeto completo) destacado, el campo de PIN con el foco inicial y los botones Cancelar/Firmar; SHALL NOT mostrar el CUIL, el sujeto completo ni la cantidad o los nombres de los documentos. SHALL aparecer centrado en la pantalla y por encima de las demás ventanas (incluido el navegador que embebe el widget). La advertencia de último intento SHALL seguir mostrándose cuando corresponda. Los nombres de los documentos SHALL seguir quedando en el registro de actividad del agente.

#### Scenario: Usuario cancela
- **WHEN** el usuario cierra el diálogo o pulsa Cancelar
- **THEN** la respuesta es `409` con `code: "user_cancelled"` y no se intentó ningún login

#### Scenario: Tiempo agotado
- **WHEN** el usuario no responde en 120 segundos
- **THEN** el diálogo se cierra y la respuesta es `409` con `code: "user_cancelled"`

#### Scenario: Nombres a mostrar
- **WHEN** el pedido trae tres documentos
- **THEN** el diálogo no muestra sus nombres ni su cantidad; los tres nombres quedan en el registro de actividad del agente

#### Scenario: Titular y colocación
- **WHEN** se abre el diálogo para un certificado con sujeto `CN=Juan Perez,serialNumber=CUIL 20111111112`
- **THEN** muestra «Juan Perez» como titular, no muestra el CUIL ni el sujeto completo, queda centrado y al frente, con el foco en el campo de PIN
