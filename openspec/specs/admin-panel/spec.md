# admin-panel Specification

## Purpose
TBD - created by archiving change panel-de-administracion. Update Purpose after archive.

## Requirements

### Requirement: Página de administración
`GET /admin` SHALL servir una página web propia (HTML, CSS y JavaScript sin dependencias externas) con secciones para solicitudes, custodia de un documento, webhooks, anclas de confianza, certificado propio y eventos de administración, que consume la API de administración. SHALL responder `404` si la administración está deshabilitada.

#### Scenario: Página disponible
- **WHEN** hay token de administración configurado
- **THEN** `/admin` responde `200` con la página y sus recursos estáticos

#### Scenario: Deshabilitada
- **WHEN** no hay token configurado
- **THEN** `/admin` y sus recursos responden `404`

### Requirement: Seguridad de la página
La página SHALL servirse con una política de seguridad de contenido que solo permita recursos del propio origen, sin scripts ni estilos en línea, SHALL prohibir ser embebida (`frame-ancestors 'none'`), SHALL no cachearse y SHALL construir el contenido con `textContent` (nunca `innerHTML`). El token SHALL guardarse en `sessionStorage` y enviarse solo en `Authorization`; la página SHALL NOT usar cookies.

#### Scenario: Cabeceras
- **WHEN** se solicita `/admin`
- **THEN** la respuesta lleva la CSP restrictiva, `X-Content-Type-Options: nosniff` y `Cache-Control: no-store`

#### Scenario: Contenido hostil
- **WHEN** un dato mostrado contiene etiquetas HTML o scripts (por ejemplo un nombre de firmante)
- **THEN** se muestra como texto y no se ejecuta

### Requirement: Uso del panel
El panel SHALL pedir el token de administración, SHALL informar con claridad un token inválido, SHALL permitir cerrar sesión borrando el token, y SHALL pedir confirmación antes de reenviar un webhook, quitar un ancla o rotar el certificado.

#### Scenario: Ingreso y listado
- **WHEN** se ingresa un token válido
- **THEN** se ve el listado de solicitudes y se pueden aplicar filtros

#### Scenario: Token inválido
- **WHEN** se ingresa un token incorrecto
- **THEN** se muestra un mensaje de acceso denegado y no se guarda el token

#### Scenario: Confirmación
- **WHEN** se pulsa "Rotar certificado"
- **THEN** no se rota hasta confirmar
