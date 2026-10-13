## MODIFIED Requirements

### Requirement: Embebido por iframe
El widget SHALL poder embeberse con un `<iframe src="{signing_url}">` desde cualquier origen listado en los `allowed_origins` del integrador, sin que el widget dependa del framework de la página anfitriona, y SHALL negarse a mostrarse dentro de cualquier otro origen. El aislamiento (`sandbox`) que aplican el Web Component, la página de ejemplo y los paneles de Firmadoc, y el que documenta la guía de integración, SHALL permitir que el widget abra una pestaña nueva fuera del aislamiento (el enlace «Continuar en el servicio de firma» de la firma remota) y descargue archivos, además de ejecutar scripts y usar su propio origen.

#### Scenario: Origen permitido
- **WHEN** una página de un origen permitido embebe `signing_url`
- **THEN** el widget se carga y funciona dentro del iframe sin recargar la página anfitriona

#### Scenario: Origen no permitido
- **WHEN** una página de otro origen intenta embeber el mismo enlace
- **THEN** el navegador bloquea el marco por la política `frame-ancestors` y el widget no se muestra

#### Scenario: Enlace al servicio de firma remota
- **WHEN** la persona elige la firma remota dentro del widget embebido con el aislamiento recomendado y pulsa «Continuar en el servicio de firma»
- **THEN** la página de autorización del servicio se abre en una pestaña nueva, sin aislamiento, y permite enviar su formulario
