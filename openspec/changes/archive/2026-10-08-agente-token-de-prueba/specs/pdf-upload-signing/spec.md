## MODIFIED Requirements

### Requirement: Firmante y método de la solicitud
Si no se informa `signer`, la solicitud SHALL registrar como firmante al configurado en `FIRMADOC_PANEL_SIGNER_NAME`, `FIRMADOC_PANEL_SIGNER_IDENTIFIER` y `FIRMADOC_PANEL_SIGNER_EMAIL` (por defecto «Operador del panel», `panel`, `panel@invalid`). La solicitud SHALL permitir elegir en el widget todos los métodos habilitados en el servidor, usando como método inicial el primero disponible en el orden `token`, `firmar`, `local`.

#### Scenario: Firmante por defecto
- **WHEN** se carga un PDF sin `signer`
- **THEN** la solicitud queda con el firmante «Operador del panel» y la firma completada refleja el sujeto del certificado usado

#### Scenario: Firmante configurado
- **WHEN** la configuración define el firmante del panel con un CUIL y se carga un PDF sin `signer`
- **THEN** la solicitud queda con ese nombre y CUIL, y la firma con token exige un certificado con ese CUIL

#### Scenario: Métodos
- **WHEN** el servidor está en modo real (el proveedor `local` no se admite)
- **THEN** la solicitud no ofrece `local` y el widget solo ofrece los demás métodos habilitados
