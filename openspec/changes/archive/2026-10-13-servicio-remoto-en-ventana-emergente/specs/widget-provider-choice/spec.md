## MODIFIED Requirements

### Requirement: Firma remota desde el widget
Con el proveedor `firmar`, el widget SHALL mostrar una pantalla de confirmación, enviar el documento al servicio con `prepare`, mostrar el enlace "Continuar en el servicio de firma" (nunca abierto automáticamente) y consultar el estado de la solicitud periódicamente hasta que sea `signed` o `failed`, mostrando entonces la firma completada o el error y notificando al sistema anfitrión como en los demás métodos. Al pulsar el enlace, el widget SHALL abrir el servicio en una ventana emergente acotada y centrada sobre la del panel; si el navegador la bloquea, el enlace SHALL abrirse en una pestaña (`target="_blank"` con `rel="noreferrer"`). Cuando la espera termina (firmada, rechazada, vencida o cancelada) el widget SHALL cerrar esa ventana si sigue abierta.

#### Scenario: Firma remota exitosa
- **WHEN** el servicio informa la firma y la solicitud pasa a `signed`
- **THEN** el widget muestra la firma completada, cierra la ventana del servicio y notifica `signed` al anfitrión

#### Scenario: Rechazo del servicio
- **WHEN** la solicitud pasa a `failed`
- **THEN** el widget muestra el error, cierra la ventana del servicio y notifica `failed` al anfitrión

#### Scenario: Servicio no disponible
- **WHEN** `prepare` responde `503`
- **THEN** se muestra que el servicio remoto no está disponible y se puede reintentar, elegir otro método o cancelar

#### Scenario: Recarga con la firma remota en curso
- **WHEN** se abre el widget con una solicitud `firmar` en `signing`
- **THEN** se muestra la espera sin enlace y se sigue consultando el estado

#### Scenario: Sondeo acotado
- **WHEN** se sale de la pantalla de espera
- **THEN** se deja de consultar el estado

#### Scenario: Ventana emergente bloqueada
- **WHEN** el navegador no permite abrir la ventana emergente
- **THEN** el enlace abre el servicio en una pestaña y la espera continúa igual
