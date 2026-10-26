## ADDED Requirements

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

## MODIFIED Requirements

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
