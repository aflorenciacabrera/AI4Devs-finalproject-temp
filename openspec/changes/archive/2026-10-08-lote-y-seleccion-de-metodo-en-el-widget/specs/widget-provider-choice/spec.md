## ADDED Requirements

### Requirement: Métodos como tarjetas con validez
El widget SHALL mostrar los métodos de firma como tarjetas con título, descripción y una etiqueta de validez: «FIRMA DIGITAL» para `token`, «FIRMAR» para la firma remota y «DEMOSTRACIÓN» para la propia, aclarando en esta última que es firma electrónica sin la presunción legal de la firma digital. Las tarjetas SHALL poder elegirse con el teclado.

#### Scenario: Etiquetas
- **WHEN** se muestra la elección con los tres métodos
- **THEN** cada tarjeta lleva su etiqueta y la de demostración aclara que no tiene presunción legal

### Requirement: Token preseleccionado con estado del agente
Cuando `token` esté entre los métodos permitidos, el widget SHALL consultar al agente local y, si responde, preseleccionar el token y mostrar «Firmadoc Agent conectado · token detectado». Si el agente no responde, SHALL mostrar que no se detectó el agente sin impedir elegir otro método.

#### Scenario: Agente conectado
- **WHEN** el agente responde con un token presente
- **THEN** la tarjeta del token queda preseleccionada con el indicador de conexión

#### Scenario: Agente ausente
- **WHEN** el agente no responde
- **THEN** la tarjeta indica que no se detectó el agente y el resto de los métodos siguen disponibles

### Requirement: Tarjeta del documento
El widget SHALL mostrar el documento a firmar con su nombre, páginas, tamaño y estado «Pendiente de firma» con su vencimiento cuando exista. El contexto del widget SHALL incluir `signing_status`, `signature_deadline`, `page_count` y `size_bytes` del documento vigente, sin el binario.

#### Scenario: Documento con vencimiento
- **WHEN** el documento está pendiente de firma con fecha límite
- **THEN** la tarjeta muestra «Pendiente de firma» y «Vence dd/mm/aaaa»

#### Scenario: Sin vencimiento
- **WHEN** el documento no tiene fecha límite
- **THEN** la tarjeta muestra el estado sin vencimiento

#### Scenario: Contexto sin binarios
- **WHEN** se pide el contexto del widget
- **THEN** incluye `signing_status`, `signature_deadline`, `page_count` y `size_bytes` y ningún PDF

### Requirement: Certificados con vigencia
La lista de certificados SHALL mostrar el emisor y la vigencia de cada uno y deshabilitar los vencidos indicando «Venció el dd/mm/aaaa». La elección de un certificado rechazado por el servidor SHALL mostrar el motivo antes de pedir el PIN.

#### Scenario: Certificado vencido
- **WHEN** el token tiene un certificado vencido
- **THEN** aparece deshabilitado con su fecha de vencimiento y no puede elegirse
