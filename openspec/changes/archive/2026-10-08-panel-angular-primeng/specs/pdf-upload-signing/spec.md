## MODIFIED Requirements

### Requirement: Sistema integrador interno del panel
Los documentos cargados desde el panel SHALL pertenecer a un sistema integrador reservado llamado «Firmadoc (panel)», creado la primera vez que se necesita. Sus orígenes permitidos SHALL ser el origen de `public_base_url` más los de `FIRMADOC_PANEL_ORIGINS` (lista separada por comas, vacía por defecto; pensada para el servidor de desarrollo del panel Angular), y SHALL sincronizarse con la configuración vigente en cada carga desde el panel. Su API key SHALL generarse al azar y no mostrarse nunca, de modo que no pueda usarse en la API de integradores.

#### Scenario: Creación diferida
- **WHEN** se hace la primera carga desde el panel
- **THEN** se crea el sistema interno; las cargas siguientes lo reutilizan sin duplicarlo

#### Scenario: Orígenes extra para el servidor de desarrollo
- **WHEN** `FIRMADOC_PANEL_ORIGINS=http://localhost:4200` y se carga un PDF desde el panel
- **THEN** la página del widget de esa solicitud responde `frame-ancestors` con el origen de `public_base_url` y `http://localhost:4200`

#### Scenario: Cambio de configuración
- **WHEN** el sistema interno ya existía con otros orígenes y cambia la configuración
- **THEN** la siguiente carga desde el panel actualiza sus orígenes permitidos sin duplicar el sistema

#### Scenario: Sin acceso por API key
- **WHEN** alguien intenta autenticarse en la API de integradores con cualquier clave contra ese sistema
- **THEN** responde `401`
