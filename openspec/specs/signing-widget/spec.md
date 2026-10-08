# Signing Widget Specification

## Purpose

Comportamiento de la interfaz de firma: flujos token y local, estados, errores traducidos, accesibilidad y ausencia de datos sensibles en el navegador.

## Requirements

### Requirement: Arranque con el token de la URL
Al cargarse, el widget SHALL leer el token del fragmento de la URL (`#t=...`), borrarlo de la barra de direcciones y del historial, mantenerlo solo en memoria y pedir el contexto de la solicitud; si falta el token o el servidor responde `401` SHALL mostrar que el enlace de firma no es válido o venció, sin ofrecer reintentos.

#### Scenario: Token en el fragmento
- **WHEN** se abre `/sign/{id}#t=<token>`
- **THEN** el widget usa ese token, la URL pasa a `/sign/{id}` sin fragmento y el token no se guarda en `localStorage` ni `sessionStorage`

#### Scenario: Enlace inválido
- **WHEN** falta el token o el servidor lo rechaza
- **THEN** se muestra "El enlace de firma no es válido o venció" con la indicación de volver al sistema de origen

### Requirement: Detección del agente y listado de certificados
Para una solicitud con proveedor `token`, el widget SHALL consultar `GET {agent_url}/certificates`, mostrar el estado del agente y listar los certificados (nombre, CUIL, emisor, vigencia), deshabilitando y explicando los ya vencidos.

#### Scenario: Agente con token
- **WHEN** el agente responde con certificados
- **THEN** se muestra "Firmadoc Agent conectado" y la lista, con el primer certificado vigente preseleccionado

#### Scenario: Agente no detectado
- **WHEN** no hay respuesta del agente
- **THEN** se muestra "No detectamos Firmadoc Agent" con la lista de comprobaciones (agente abierto, token conectado, sitio autorizado en el agente, permiso de red local del navegador) y los botones "Reintentar detección" y "Cancelar"

#### Scenario: Token sin conectar
- **WHEN** el agente responde `token_not_found`
- **THEN** se indica que conecte el token y se ofrece reintentar

#### Scenario: Sitio no autorizado en el agente
- **WHEN** el agente rechaza el origen del sitio (su respuesta `403` no lleva cabeceras CORS, por lo que el navegador no permite leerla y el widget la percibe como un agente que no responde)
- **THEN** la pantalla de agente no detectado incluye entre sus comprobaciones que el sitio esté autorizado en el agente y que debe pedirlo al área de sistemas

#### Scenario: Origen rechazado con respuesta legible
- **WHEN** el agente responde `origin_not_allowed` con un cuerpo legible (por ejemplo, el widget y el agente en el mismo origen durante el desarrollo)
- **THEN** se explica que el agente de esa PC no autoriza este sitio y que debe pedirlo al área de sistemas

#### Scenario: Biblioteca del token
- **WHEN** el agente responde `pkcs11_unavailable`
- **THEN** se indica que el software del fabricante del token no está instalado o no carga y se sugiere el diagnóstico del agente

### Requirement: Validación del certificado antes del PIN
Al elegir "Validar y continuar", el widget SHALL enviar el certificado a `prepare` y, si el servidor lo rechaza, SHALL mostrar el motivo traducido, aclarar que **no se pidió el PIN**, y ofrecer elegir otro certificado.

#### Scenario: Certificado revocado
- **WHEN** el servidor responde `certificate_revoked`
- **THEN** se muestra "El certificado no pudo validarse", el motivo "Certificado revocado" y "No se te pidió el PIN"

#### Scenario: Otros motivos
- **WHEN** el servidor responde `certificate_expired`, `certificate_untrusted`, `certificate_invalid` o `cuil_mismatch`
- **THEN** se muestra el motivo correspondiente en lenguaje claro, y para `cuil_mismatch` se aclara que el certificado no corresponde al firmante de la solicitud

#### Scenario: Elegir otro certificado
- **WHEN** la persona pulsa "Elegir otro certificado"
- **THEN** vuelve a la lista sin recargar la página y sin perder la sesión

### Requirement: Firma con el agente
Con el certificado validado, el widget SHALL enviar al agente los desafíos (`POST {agent_url}/sign`), mostrar "Esperando tu confirmación" indicando que el PIN se ingresa en la ventana del agente y que Firmadoc no lo recibe, y enviar las firmas a `complete`.

#### Scenario: Firma correcta
- **WHEN** el agente devuelve las firmas
- **THEN** el widget las envía a `complete` y pasa a la pantalla de firma completada

#### Scenario: Cancelación en el agente
- **WHEN** el agente responde `user_cancelled`
- **THEN** el widget vuelve a la elección del certificado indicando que se canceló, sin tratarlo como error

#### Scenario: PIN incorrecto
- **WHEN** el agente responde `pin_incorrect`
- **THEN** se informa "PIN incorrecto" y se ofrece reintentar con un botón; **el widget nunca reintenta por su cuenta**

#### Scenario: PIN bloqueado
- **WHEN** el agente responde `pin_locked`
- **THEN** se informa que el token está bloqueado y que se desbloquea con el administrador del token, sin ofrecer reintento

#### Scenario: Agente ocupado
- **WHEN** el agente responde `busy`
- **THEN** se indica que ya hay una firma esperando confirmación en esa PC

### Requirement: Desafío vencido
Si `complete` responde `409` porque el desafío venció, el widget SHALL explicar que se agotó el tiempo y ofrecer volver a empezar desde la validación del certificado.

#### Scenario: Se agotó el tiempo
- **WHEN** `complete` responde `409`
- **THEN** se muestra "Se agotó el tiempo para firmar" y un botón que repite `prepare` con el mismo certificado

### Requirement: Firma con el proveedor local
Para una solicitud con proveedor `local`, el widget SHALL mostrar el documento, aclarar que es una firma electrónica de demostración y firmar con un solo paso de confirmación (`prepare` y `complete` sin certificado ni agente).

#### Scenario: Firma de demostración
- **WHEN** la persona confirma
- **THEN** se completa la firma sin consultar al agente y se muestra la pantalla de firma completada

### Requirement: Proveedor no soportado
Para un proveedor que el widget no implementa (`firmar`), SHALL mostrar que ese método de firma no está disponible en este momento, sin intentar ninguna operación.

#### Scenario: Proveedor firmar
- **WHEN** el contexto indica `provider: firmar`
- **THEN** se muestra un mensaje de método no disponible y solo se ofrece cancelar

### Requirement: Firma completada
Al completarse, el widget SHALL mostrar firmante, fecha y hora, método, nivel de firma, certificado y versión del documento tal como los informa el servidor (sin inventar valores), y SHALL ofrecer "Descargar PDF firmado" y "Cerrar".

#### Scenario: Datos mostrados
- **WHEN** el servidor devuelve la firma completada
- **THEN** se muestran los datos devueltos, incluyendo "v2 · vigente" y que la versión original se conserva

#### Scenario: Descarga
- **WHEN** la persona pulsa "Descargar PDF firmado"
- **THEN** el navegador descarga el PDF obtenido del endpoint de descarga del widget, sin exponer el token en la URL

### Requirement: Cancelar en cualquier momento
En todas las pantallas anteriores a la firma, "Cancelar" SHALL cerrar el flujo, avisar a la página anfitriona y dejar la solicitud sin firmar.

#### Scenario: Cancelar
- **WHEN** la persona pulsa "Cancelar" antes de firmar
- **THEN** se notifica `firmadoc:cancelled` a la página anfitriona y no se realiza ninguna operación de firma

### Requirement: Accesibilidad
El widget SHALL poder usarse solo con teclado, anunciar los cambios de estado a lectores de pantalla (región `aria-live`), mover el foco al título de cada pantalla nueva, no depender solo del color para transmitir estados y no presentar violaciones de accesibilidad detectables automáticamente en ninguna pantalla.

#### Scenario: Cambio de pantalla
- **WHEN** el widget pasa a otra pantalla
- **THEN** el foco queda en su título y el cambio se anuncia

#### Scenario: Revisión automática
- **WHEN** se ejecuta la revisión de accesibilidad automática sobre cada pantalla
- **THEN** no informa violaciones

### Requirement: Sin datos sensibles en el navegador
El widget SHALL NOT pedir, mostrar ni guardar el PIN, SHALL NOT escribir el token ni las firmas en el almacenamiento del navegador ni en la consola, y SHALL NOT incluir el token en ninguna URL.

#### Scenario: Almacenamiento y consola
- **WHEN** se completa un flujo
- **THEN** `localStorage`, `sessionStorage`, las cookies y la consola no contienen el token ni las firmas
