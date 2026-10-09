# demo-mode Specification

## Purpose
TBD - created by archiving change modo-demo. Update Purpose after archive.

## Requirements

### Requirement: Entorno de demostración con un comando
`python -m firmadoc.demo` SHALL preparar un entorno de demostración aislado en `data/demo/` (base SQLite y certificado de demostración propios), aplicar las migraciones hasta la última, cargar el seed de demostración con sus PDF y arrancar el servidor en `--host` y `--port` (por defecto `127.0.0.1:8000`). Los PDF (versiones, estado intermedio de la firma y PDF del seed) SHALL guardarse dentro de la base de demostración (almacén `database`, tabla `stored_blob`), y el comando SHALL NOT crear archivos PDF en `data/demo/storage/`. SHALL configurar `FIRMADOC_PUBLIC_BASE_URL` con `http://localhost:{puerto}` y habilitar la administración, sin tocar la base ni las carpetas habituales del proyecto.

#### Scenario: Primer arranque
- **WHEN** se ejecuta el comando sin `data/demo/`
- **THEN** se crea la base con el esquema completo y el seed, los PDF del seed están en `stored_blob`, no existe ningún PDF bajo `data/demo/storage/` y el servidor queda sirviendo `/admin` y `/health`

#### Scenario: Arranque repetido
- **WHEN** se ejecuta de nuevo con `data/demo/` existente
- **THEN** se reutilizan la base y los datos sin duplicar el seed

#### Scenario: Reinicio del entorno
- **WHEN** se ejecuta con `--reset`
- **THEN** se borra `data/demo/` y se crea de nuevo

#### Scenario: Firma en la demo
- **WHEN** se carga un PDF desde el panel de la demo y se firma
- **THEN** la versión original y la firmada quedan en `stored_blob`, se descargan con el contenido correcto y no aparece ningún archivo nuevo en `data/demo/storage/`

### Requirement: Secretos estables
El comando SHALL generar una única vez un token de administración y un secreto de los enlaces del widget (de al menos 32 caracteres), guardarlos en `data/demo/demo.json` y reutilizarlos en los arranques siguientes.

#### Scenario: Secretos conservados
- **WHEN** se prepara el entorno dos veces
- **THEN** el token de administración y el secreto son los mismos

### Requirement: Solo demostración
El comando SHALL negarse a arrancar con código de salida distinto de cero y un mensaje claro si `FIRMADOC_REAL_MODE` está activo, y SHALL NOT habilitar ni relajar el modo real.

#### Scenario: Modo real activo
- **WHEN** `FIRMADOC_REAL_MODE=true` en el entorno
- **THEN** el comando termina con error sin crear ni modificar `data/demo/`

### Requirement: Guía al arrancar
Al arrancar el comando SHALL mostrar la URL del panel, el token de administración, la API key de demostración y el método a usar sin token («Firma propia»), y SHALL avisar, sin impedir el arranque, si el widget no está compilado indicando cómo compilarlo.

#### Scenario: Widget sin compilar
- **WHEN** no existe `widget/dist/index.html`
- **THEN** el servidor arranca y el aviso indica `npm run build` en `widget/`

#### Scenario: Datos de acceso
- **WHEN** el entorno está listo
- **THEN** se imprime la URL de `/admin`, el token de administración y el uso de «Firma propia»

### Requirement: Token de prueba para firmar con el agente
El modo demostración SHALL generar una vez, en `data/demo/token/`, una AC de prueba (`ca.crt`) y un certificado de firmante con clave privada (`firmante.pem`) cuyo sujeto lleve el CUIL `20000000001` («Firmante de Prueba»), y SHALL reutilizarlos en arranques siguientes. SHALL armar un directorio de confianza propio (`data/demo/trust/`) con las anclas del repositorio más la AC de prueba y apuntar `FIRMADOC_TRUST_DIR` a él, sin modificar `backend/trust`. SHALL configurar al firmante del panel con ese nombre y CUIL para que la validación del certificado del token de prueba pase. La guía SHALL imprimir el comando del agente con token de software y el PIN `1234`.

#### Scenario: Primer arranque
- **WHEN** se prepara la demo en una carpeta vacía
- **THEN** existen `data/demo/token/ca.crt` y `firmante.pem`, el certificado está firmado por esa AC y lleva `CUIL 20000000001`, y `data/demo/trust/` contiene la AC de prueba

#### Scenario: Arranques siguientes
- **WHEN** se prepara la demo de nuevo sin `--reset`
- **THEN** la AC y el certificado son los mismos (misma huella)

#### Scenario: Guía
- **WHEN** arranca la demo
- **THEN** la guía muestra `firmadoc-agent run --software-token data/demo/token/firmante.pem --origin http://localhost:<puerto>` y el PIN `1234`

#### Scenario: Validación del certificado de prueba
- **WHEN** el agente de prueba presenta su certificado en `prepare` para una solicitud cargada desde el panel de la demo
- **THEN** el servidor lo acepta (cadena hasta la AC de prueba y CUIL del firmante del panel)

### Requirement: PDF de arranques anteriores pasan a la base
Si al preparar el entorno existen en `data/demo/storage/` binarios de versiones registradas en la base de demostración (entornos creados cuando la demo guardaba los PDF en disco), el comando SHALL copiarlos a `stored_blob` antes de arrancar, verificando cada uno contra el hash de su versión, SHALL NOT borrar los archivos y SHALL informar en la guía cuántos copió. Si alguna versión no se puede copiar (archivo ausente, corrupto o distinto del que ya está en la base), el comando SHALL informar cada problema y terminar con código distinto de cero sin arrancar el servidor. La copia SHALL ser idempotente.

#### Scenario: Entorno con PDF en disco
- **WHEN** `data/demo/` tiene versiones cuyos PDF están en `data/demo/storage/` y no en la base
- **THEN** al arrancar quedan en `stored_blob`, los archivos siguen en disco, la guía informa cuántos se copiaron y los documentos se descargan igual que antes

#### Scenario: Arranque siguiente
- **WHEN** se vuelve a arrancar la demo
- **THEN** no se copia nada y la guía no menciona la copia

#### Scenario: PDF ausente o corrupto
- **WHEN** falta el archivo de una versión registrada o su contenido no coincide con el hash de la versión
- **THEN** el comando informa la versión afectada y termina con error sin arrancar el servidor
