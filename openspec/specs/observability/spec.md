# observability Specification

## Purpose
Registros estructurados del servidor con un identificador por pedido, para investigar una firma concreta sin exponer datos sensibles, y un SLO de firma medible desde esos registros (FIRDOC-66).

## Requirements
### Requirement: Identificador de pedido
El servidor SHALL asignar a cada pedido HTTP un identificador, devolverlo en la cabecera de respuesta `X-Request-ID` e incluirlo en todos los registros que ese pedido produzca. SHALL aceptar el identificador que mande quien llama en `X-Request-ID` solo si tiene entre 8 y 64 caracteres de `A-Z a-z 0-9 . _ -`; en cualquier otro caso SHALL generar uno nuevo.

#### Scenario: Pedido sin identificador
- **WHEN** llega un pedido sin `X-Request-ID`
- **THEN** la respuesta lleva un `X-Request-ID` generado por el servidor, distinto en cada pedido

#### Scenario: Identificador del integrador
- **WHEN** llega un pedido con un `X-Request-ID` de forma válida
- **THEN** la respuesta y los registros usan ese mismo identificador

#### Scenario: Identificador con forma inválida
- **WHEN** el `X-Request-ID` recibido tiene espacios, comillas, saltos de línea o más de 64 caracteres
- **THEN** se descarta y se genera uno nuevo

### Requirement: Registros estructurados
El servidor SHALL escribir en la salida estándar una línea JSON por pedido HTTP (`http_request`, con método, ruta declarada, estado y duración) y una por evento de auditoría (`audit.<tipo>`, con `signature_request_id` o `batch_id`). `/health` SHALL registrarse en nivel `debug`. El formato (`json` o `text`) y el nivel SHALL configurarse con `FIRMADOC_LOG_FORMAT` y `FIRMADOC_LOG_LEVEL`, y un valor inválido SHALL rechazarse al cargar la configuración.

#### Scenario: Firma completa
- **WHEN** se crea, prepara y completa una solicitud de firma
- **THEN** quedan los eventos `audit.created`, `audit.prepared` y `audit.signed` con el `signature_request_id`, y el de `signed` comparte `request_id` con el pedido de `complete`

#### Scenario: Error del dominio
- **WHEN** un pedido termina en `404`, `409` o `422`
- **THEN** su registro `http_request` lleva ese estado

### Requirement: Nada sensible en los registros
Los registros SHALL NOT contener el PIN, tokens, API keys, secretos, el contenido de documentos, firmas ni certificados, la cadena de consulta de la URL, ni datos personales del firmante (nombre, CUIL, correo). Si un campo con nombre sensible llegara a un registro, su valor SHALL reemplazarse por `[omitido]`.

#### Scenario: Firma con datos del firmante
- **WHEN** se firma un documento de un firmante con nombre, CUIL y correo
- **THEN** ninguno de esos valores, ni la API key, ni el PDF aparecen en los registros

#### Scenario: Campo sensible por error
- **WHEN** el código registra un evento con un campo llamado `pin`, `api_key`, `cuil` o `email`
- **THEN** el registro lleva `[omitido]` en lugar del valor

### Requirement: SLO de firma medible
El repositorio SHALL documentar un SLO de firma (indicadores, objetivo, ventana, presupuesto de error y alerta por tasa de consumo) e incluir una herramienta (`python -m firmadoc.slo`) que lo calcule desde los registros: cuenta los pedidos cuya ruta termina en `/prepare` o `/complete`, toma como malos los de estado 500 o más (disponibilidad) y además los que superan el umbral de latencia, ignora las líneas que no son JSON y, con `--fail-on-breach`, termina con código 1 si no se cumple el objetivo.

#### Scenario: Rechazo correcto
- **WHEN** un pedido de firma termina en `409` o `422`
- **THEN** cuenta como bueno

#### Scenario: Borde de latencia
- **WHEN** un pedido tarda exactamente el umbral
- **THEN** cuenta como bueno, y uno que lo supera cuenta como malo

#### Scenario: Sin pedidos
- **WHEN** los registros no tienen pedidos de firma
- **THEN** no se informa un incumplimiento y se avisa que la muestra es chica
