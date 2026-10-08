## MODIFIED Requirements

### Requirement: Proveedor no soportado
Para un proveedor que el widget no conoce, SHALL mostrar que ese método de firma no está disponible en este momento, sin intentar ninguna operación. Los proveedores `token`, `local` y `firmar` SHALL estar soportados.

#### Scenario: Proveedor desconocido
- **WHEN** el contexto indica un proveedor que el widget no implementa
- **THEN** se muestra un mensaje de método no disponible y solo se ofrece cancelar

#### Scenario: Proveedor firmar
- **WHEN** el contexto indica `provider: firmar`
- **THEN** se sigue el flujo de firma remota y no se muestra el mensaje de método no disponible
