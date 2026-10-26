## ADDED Requirements

### Requirement: Firmante real para el token físico
El comando de la demo SHALL aceptar `--cuil <11 dígitos>`, `--nombre <titular>` y, opcionalmente, `--email <correo>` para configurar al firmante del panel con los datos del titular de un token físico. `--cuil` y `--nombre` SHALL indicarse juntos; `--cuil` SHALL tener exactamente 11 dígitos (se admiten guiones, que se descartan). Sin `--email`, el correo del firmante SHALL ser `<cuil>@invalid`. Sin estos parámetros, el firmante del panel SHALL seguir siendo el del token de prueba. El token de prueba y su AC SHALL seguir generándose aunque se indique un firmante real, para no romper el camino con token de software.

#### Scenario: Firmante real indicado
- **WHEN** se arranca la demo con `--cuil 20-12345678-9 --nombre "Titular del Token"`
- **THEN** el firmante del panel es «Titular del Token», CUIL `20123456789`, correo `20123456789@invalid`, y la guía lo muestra

#### Scenario: Parámetros incompletos o inválidos
- **WHEN** se indica `--cuil` sin `--nombre`, `--nombre` sin `--cuil`, o un CUIL que no tenga 11 dígitos
- **THEN** el comando termina con error antes de preparar nada y explica el parámetro faltante o inválido

#### Scenario: Sin parámetros
- **WHEN** se arranca la demo sin `--cuil` ni `--nombre`
- **THEN** el firmante del panel es «Firmante de Prueba», CUIL `20000000001`, como hasta ahora

#### Scenario: Validación del certificado real
- **WHEN** el agente con el módulo PKCS#11 presenta en `prepare` el certificado del token físico, cuya AC emisora está entre las anclas de `backend/trust/`, para una solicitud cargada desde el panel de una demo arrancada con el CUIL de ese certificado
- **THEN** el servidor acepta el certificado (cadena de confianza y CUIL coincidente) y el agente pide el PIN

## MODIFIED Requirements

### Requirement: Guía al arrancar
Al arrancar el comando SHALL mostrar la URL del panel, el token de administración, la API key de demostración, el método a usar sin token («Firma propia») y el firmante configurado para el panel (nombre y CUIL), y SHALL avisar, sin impedir el arranque, si el widget no está compilado indicando cómo compilarlo. La guía SHALL mostrar además el comando del agente para firmar con un token físico, con el módulo PKCS#11 de `%APPDATA%\FirmadocAgent\config.json` y el origen de la demo (`python -m firmadoc_agent --config "%APPDATA%\FirmadocAgent\config.json" run --origin http://localhost:<puerto>`), e indicar que el PIN es el del token.

#### Scenario: Widget sin compilar
- **WHEN** no existe `widget/dist/index.html`
- **THEN** el servidor arranca y el aviso indica `npm run build` en `widget/`

#### Scenario: Datos de acceso
- **WHEN** el entorno está listo
- **THEN** se imprime la URL de `/admin`, el token de administración, el uso de «Firma propia» y el firmante del panel

#### Scenario: Comando para el token físico
- **WHEN** arranca la demo en el puerto 8200
- **THEN** la guía muestra `python -m firmadoc_agent --config "%APPDATA%\FirmadocAgent\config.json" run --origin http://localhost:8200` y aclara que con un token físico el PIN es el del propio token
