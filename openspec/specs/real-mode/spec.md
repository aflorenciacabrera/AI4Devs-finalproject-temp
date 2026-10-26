# real-mode Specification

## Purpose
TBD - created by archiving change modo-real. Update Purpose after archive.

## Requirements

### Requirement: Modo real
`FIRMADOC_REAL_MODE=true` SHALL activar el modo real; por defecto SHALL estar apagado y el comportamiento SHALL ser el de demostración, sin cambios.

#### Scenario: Valor por defecto
- **WHEN** no se configura `FIRMADOC_REAL_MODE`
- **THEN** el servidor se comporta como hasta ahora

### Requirement: Verificación previa de la configuración
Firmadoc SHALL ofrecer una verificación previa de la configuración (`python -m firmadoc.preflight`, código de salida distinto de cero si hay errores) que informe errores, advertencias e información. En modo real SHALL considerarse **error**: falta de `FIRMADOC_SIGNING_SECRET`; revocación distinta de `hard-fail`; `hard-fail` sin ninguna fuente de revocación (ni consulta por red ni CRL local); ninguna ancla raíz en el directorio de confianza; servicio de firma remota simulado habilitado; webhooks que permiten `http` o hosts privados. SHALL ser **advertencia**: base SQLite, `FIRMADOC_PUBLIC_BASE_URL` sin `https` (salvo `localhost`), administración sin token, almacén de documentos en disco. Fuera del modo real los mismos hallazgos SHALL informarse como advertencias.

#### Scenario: Configuración correcta
- **WHEN** la configuración cumple todos los requisitos del modo real
- **THEN** no hay errores y el comando termina con código 0

#### Scenario: Varios errores
- **WHEN** faltan el secreto y las anclas y la revocación es `soft-fail`
- **THEN** se informan los tres errores juntos y el comando termina con código distinto de cero

#### Scenario: Revocación estricta sin fuentes
- **WHEN** la revocación es `hard-fail`, la consulta por red está apagada y no hay CRL locales
- **THEN** se informa un error

#### Scenario: Modo demostración
- **WHEN** se ejecuta con el modo real apagado
- **THEN** los hallazgos se informan como advertencias y el código de salida es 0

### Requirement: Arranque seguro
En modo real el servidor SHALL ejecutar la verificación previa al arrancar y SHALL negarse a arrancar, indicando todos los errores, si hay alguno.

#### Scenario: Configuración insegura
- **WHEN** se inicia el servidor en modo real con errores de configuración
- **THEN** el arranque falla con la lista de errores y no se atienden pedidos

#### Scenario: Configuración válida
- **WHEN** no hay errores
- **THEN** el servidor arranca normalmente

### Requirement: Sin firma de demostración en modo real
En modo real el proveedor `local` SHALL no estar habilitado: crear una solicitud `local`, o incluirlo en `allowed_providers`, SHALL responder `422` indicando que no está habilitado. Los proveedores `token` y `firmar` (este último solo con servicio configurado) SHALL seguir disponibles.

#### Scenario: Solicitud local
- **WHEN** se crea una solicitud con `provider: local` en modo real
- **THEN** responde `422` y no se crea nada

#### Scenario: Solicitud token
- **WHEN** se crea una solicitud con `provider: token` en modo real
- **THEN** se crea normalmente

### Requirement: Sin datos de demostración en modo real
`python -m firmadoc.seed` SHALL negarse a cargar los datos de demostración en modo real, con un mensaje claro y código de salida distinto de cero, sin modificar la base.

#### Scenario: Seed en modo real
- **WHEN** se ejecuta el seed con el modo real activo
- **THEN** no se carga nada y el comando falla indicando que use `firmadoc.integrators`

### Requirement: Guía de puesta en modo real
`docs/real-mode.md` SHALL documentar el paso a modo real con un token físico: instalación del software del fabricante, configuración del agente (`pkcs11_module`), diagnóstico sin PIN, carga de las anclas de la AC con confirmación de huella, ajuste del CUIL, variables requeridas, creación de integradores reales y la lista de lo que aún no está probado con hardware.

#### Scenario: Pasos y límites
- **WHEN** se lee la guía
- **THEN** contiene los pasos, un ejemplo de configuración válida para la verificación previa y las limitaciones sin probar
