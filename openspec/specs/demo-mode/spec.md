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
Si al preparar el entorno con la base propia de `data/demo/` existen en `data/demo/storage/` binarios de versiones registradas (entornos creados cuando la demo guardaba los PDF en disco), el comando SHALL copiarlos a `stored_blob` antes de arrancar, verificando cada uno contra el hash de su versión, SHALL NOT borrar los archivos y SHALL informar en la guía cuántos copió. Si alguna versión no se puede copiar (archivo ausente, corrupto o distinto del que ya está en la base), el comando SHALL informar cada problema, sugerir `--reset` y terminar con código distinto de cero sin arrancar el servidor. La copia SHALL ser idempotente. Con una base externa (`--database-url`) el comando SHALL NOT copiar nada desde `data/demo/storage/` (esa carpeta pertenece a la base propia) y SHALL comprobar que toda versión registrada en la base externa tenga su binario en `stored_blob`; si alguna no lo tiene, SHALL informar cada una, indicar cómo migrarlas desde su carpeta (`storage_migrate` con `FIRMADOC_STORAGE_DIR`) o recrear la base, sin sugerir `--reset`, y terminar con código distinto de cero sin arrancar.

#### Scenario: Entorno con PDF en disco
- **WHEN** `data/demo/` tiene versiones cuyos PDF están en `data/demo/storage/` y no en la base
- **THEN** al arrancar quedan en `stored_blob`, los archivos siguen en disco, la guía informa cuántos se copiaron y los documentos se descargan igual que antes

#### Scenario: Arranque siguiente
- **WHEN** se vuelve a arrancar la demo
- **THEN** no se copia nada y la guía no menciona la copia

#### Scenario: PDF ausente o corrupto
- **WHEN** falta el archivo de una versión registrada o su contenido no coincide con el hash de la versión
- **THEN** el comando informa la versión afectada y termina con error sin arrancar el servidor

#### Scenario: Base externa con versiones sin PDF
- **WHEN** la base de `--database-url` tiene versiones sin binario en `stored_blob`
- **THEN** el comando informa cada versión, indica cómo migrarlas o recrear la base, no sugiere `--reset` y no arranca

#### Scenario: Base externa y archivos de la demo SQLite en disco
- **WHEN** `data/demo/storage/` tiene PDF de una demo SQLite anterior y se arranca con `--database-url` contra una base cuyas versiones tienen su binario
- **THEN** la demo arranca sin copiar ni comparar esos archivos

### Requirement: Demo sobre una base externa
`python -m firmadoc.demo --database-url <url>` SHALL usar esa base de datos (URL de SQLAlchemy, por ejemplo `postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc`) en lugar de la SQLite de `data/demo/`: SHALL aplicar las migraciones hasta la última, cargar el seed de demostración si no está y guardar los PDF en `stored_blob` de esa base. Todo lo demás del entorno (secretos, token de prueba, directorio de confianza, certificado de «Firma propia», `FIRMADOC_PUBLIC_BASE_URL`, guía) SHALL seguir en `data/demo/` y comportarse igual. La guía SHALL mostrar la base en uso sin la contraseña. `--reset` SHALL borrar solo `data/demo/` y SHALL NOT modificar la base externa; con una base externa la guía SHALL indicar cómo empezar de cero (`docker compose down -v` para la base del proyecto). Una URL que no se puede interpretar SHALL rechazarse con un mensaje claro y código de salida distinto de cero, sin crear ni modificar nada.

#### Scenario: Demo contra PostgreSQL
- **WHEN** se ejecuta con `--database-url` apuntando a la base PostgreSQL del proyecto, vacía o ya migrada
- **THEN** la base queda con el esquema completo y el seed, los PDF del seed están en su `stored_blob`, se puede cargar y firmar un PDF con «Firma propia» y sus versiones quedan en `stored_blob` de esa base, y la guía muestra la base sin la contraseña

#### Scenario: Arranque repetido
- **WHEN** se ejecuta de nuevo contra la misma base
- **THEN** no duplica el seed y reutiliza los secretos y el token de prueba de `data/demo/`

#### Scenario: Reinicio con base externa
- **WHEN** se ejecuta con `--reset` y `--database-url`
- **THEN** se borra y recrea `data/demo/`, la base externa conserva sus datos y la guía indica cómo recrearla

#### Scenario: URL inválida
- **WHEN** `--database-url` no es una URL de SQLAlchemy
- **THEN** el comando termina con error sin crear `data/demo/`

#### Scenario: Sin la opción
- **WHEN** se ejecuta sin `--database-url`
- **THEN** usa `data/demo/firmadoc-demo.db` como hasta ahora
