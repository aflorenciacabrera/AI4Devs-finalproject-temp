## ADDED Requirements

### Requirement: Modo con token de software
`firmadoc-agent run --software-token RUTA` SHALL arrancar el agente con el certificado y la clave privada leídos de un archivo PEM, como único certificado del «token», aceptando como PIN `1234`, con la ventana real de confirmación y sin requerir `config.json` ni módulo PKCS#11. Los orígenes permitidos SHALL poder indicarse con `--origin` (repetible; reemplaza a los del archivo de configuración si lo hay) y el puerto con `--port`. El registro de actividad SHALL dejar constancia de que se usa un token de software. `firmadoc-agent diagnose --software-token RUTA` SHALL describir ese certificado. Es un modo de demostración: SHALL rechazar un PEM sin clave privada o sin certificado con un mensaje claro.

#### Scenario: Arranque con token de software
- **WHEN** se ejecuta `firmadoc-agent run --software-token data/demo/token/firmante.pem --origin http://localhost:8000`
- **THEN** `GET /certificates` desde ese origen devuelve el certificado del PEM y `POST /sign` firma con su clave tras confirmar con el PIN `1234`

#### Scenario: PEM inválido
- **WHEN** el archivo no contiene una clave privada y un certificado
- **THEN** el agente no arranca y explica qué falta

#### Scenario: Sin configuración
- **WHEN** no existe `config.json` y se pasa `--software-token` con `--origin`
- **THEN** el agente arranca con el puerto por defecto y esos orígenes
