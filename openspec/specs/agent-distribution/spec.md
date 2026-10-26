# Agent Distribution Specification

## Purpose

Configuración, diagnóstico sin PIN, instancia única, registro acotado y empaquetado e instalación del agente para Windows.

## Requirements

### Requirement: Configuración por archivo
El agente SHALL leer su configuración de un archivo JSON (por defecto `%APPDATA%\FirmadocAgent\config.json`, sobrescribible con `FIRMADOC_AGENT_CONFIG`) con `port`, `allowed_origins`, `pkcs11_module` y `log_level`; los valores faltantes SHALL tomar los predeterminados y los inválidos SHALL impedir el arranque con un mensaje claro.

#### Scenario: Valores por defecto
- **WHEN** el archivo no existe
- **THEN** el agente arranca en el puerto predeterminado con lista de orígenes vacía y lo informa en el registro

#### Scenario: Origen mal formado
- **WHEN** `allowed_origins` contiene `https://*.example.org` o una URL con ruta
- **THEN** el agente no arranca y explica que los orígenes deben ser `esquema://host[:puerto]` exactos

### Requirement: Comando de diagnóstico sin PIN
El agente SHALL ofrecer `firmadoc-agent diagnose`, que verifica que la biblioteca PKCS#11 cargue, lista los slots y tokens, y por cada certificado muestra sujeto, emisor, serie, vigencia, uso de clave y el atributo `serialNumber` del sujeto, sin pedir nunca el PIN ni abrir sesión.

#### Scenario: Diagnóstico con token
- **WHEN** se ejecuta el diagnóstico con un token conectado
- **THEN** imprime la ruta de la biblioteca, el token y sus certificados, y termina con código de salida 0

#### Scenario: Biblioteca inexistente
- **WHEN** el módulo configurado no existe
- **THEN** imprime el motivo, sugiere revisar la arquitectura (32/64 bits) y termina con código distinto de 0

#### Scenario: Confirmación del CUIL
- **WHEN** el certificado trae `serialNumber` con formato de CUIL
- **THEN** el diagnóstico lo muestra tal cual, para confirmar con un certificado real dónde está el CUIL

### Requirement: Instancia única
El agente SHALL NOT permitir dos instancias en el mismo puerto; si el puerto está ocupado SHALL terminar con un mensaje que lo explique.

#### Scenario: Segundo arranque
- **WHEN** se inicia el agente con el puerto ya ocupado por otra instancia
- **THEN** termina con código distinto de 0 y mensaje "ya hay una instancia o el puerto está en uso"

### Requirement: Registro de actividad acotado
El agente SHALL escribir un registro en el directorio de datos del usuario, con rotación por tamaño, sin PIN, firmas ni hashes completos, e incluyendo origen, operación, nombres de documentos y resultado.

#### Scenario: Rotación
- **WHEN** el archivo de registro supera 1 MiB
- **THEN** se rota conservando como máximo 3 archivos

### Requirement: Ejecutable único para Windows
El proyecto SHALL producir con PyInstaller un ejecutable único sin consola que incluya el intérprete y sus dependencias, e instalable sin privilegios de administrador.

#### Scenario: Compilación
- **WHEN** se ejecuta el script de compilación
- **THEN** se genera `firmadoc-agent.exe` que responde a `--version` y a `diagnose`

### Requirement: Instalación por usuario
Los scripts de instalación SHALL copiar el ejecutable a `%LOCALAPPDATA%\FirmadocAgent`, crear una configuración inicial a partir de parámetros (origen permitido y módulo PKCS#11), registrar el arranque con la sesión del usuario (clave `Run` de `HKCU`) y poder revertirse con un script de desinstalación.

#### Scenario: Instalación
- **WHEN** se ejecuta `install.ps1 -Origin https://firmadoc.example.org -Pkcs11Module <ruta>`
- **THEN** quedan instalados el ejecutable, la configuración y el arranque automático, sin pedir elevación

#### Scenario: Desinstalación
- **WHEN** se ejecuta `uninstall.ps1`
- **THEN** se detiene el agente y se eliminan el ejecutable, el arranque automático y los archivos de la aplicación, conservando opcionalmente el registro

### Requirement: Documentación de despliegue
`agent/README.md` SHALL documentar la instalación manual, el despliegue por política de dominio, la política de Chrome/Edge `LocalNetworkAccessAllowedForUrls` y el procedimiento de prueba manual con un token físico.

#### Scenario: Política del navegador
- **WHEN** un administrador busca cómo evitar el aviso de acceso a la red local
- **THEN** encuentra la política, el valor a configurar y el origen al que debe apuntar

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
