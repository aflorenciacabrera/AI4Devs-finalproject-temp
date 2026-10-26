## MODIFIED Requirements

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

## ADDED Requirements

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
