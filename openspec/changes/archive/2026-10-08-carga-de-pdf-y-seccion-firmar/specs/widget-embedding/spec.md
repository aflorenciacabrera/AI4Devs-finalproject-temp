## ADDED Requirements

### Requirement: Embebido por el propio servidor
La página de firma SHALL poder embeberse desde el origen del propio servidor cuando la solicitud pertenece al sistema integrador interno del panel, porque su `frame-ancestors` se calcula con los orígenes permitidos del sistema (el origen de `public_base_url`). Para cualquier otro sistema SHALL mantenerse la regla vigente de usar solo sus orígenes permitidos.

#### Scenario: Solicitud del panel
- **WHEN** se pide `/sign/{id}` de una solicitud creada desde el panel
- **THEN** `frame-ancestors` contiene el origen del servidor y el panel puede embeberla

#### Scenario: Solicitud de otro integrador
- **WHEN** se pide `/sign/{id}` de una solicitud de un integrador externo
- **THEN** `frame-ancestors` contiene solo los orígenes de ese integrador; el panel no puede embeberla
