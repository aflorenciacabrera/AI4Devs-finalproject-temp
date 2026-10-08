# database-storage Specification

## Purpose
TBD - created by archiving change base-de-datos-real. Update Purpose after archive.

## Requirements

### Requirement: Elección del almacén de documentos
`FIRMADOC_STORAGE_BACKEND` SHALL admitir `files` (valor por defecto, archivos en disco) y `database` (tabla `stored_blob`); cualquier otro valor SHALL rechazarse al cargar la configuración. Con `database` todos los binarios (versiones y estado intermedio de la firma) SHALL guardarse en la base de datos y ninguno en disco.

#### Scenario: Valor por defecto
- **WHEN** no se configura el almacén
- **THEN** se usan archivos en disco, sin cambios de comportamiento

#### Scenario: Valor inválido
- **WHEN** `FIRMADOC_STORAGE_BACKEND` es otro valor
- **THEN** la configuración se rechaza

#### Scenario: Todo en la base
- **WHEN** se completa una firma con el almacén `database`
- **THEN** los PDF de las versiones están en `stored_blob` y el directorio de archivos no se crea

### Requirement: Binarios atómicos con su versión
Con el almacén `database`, guardar un binario SHALL ocurrir en la misma transacción que el resto de la operación: si la operación falla o se revierte, el binario SHALL no existir.

#### Scenario: Operación revertida
- **WHEN** la creación de una versión falla después de guardar su binario
- **THEN** no queda ningún binario en `stored_blob`

#### Scenario: Operación confirmada
- **WHEN** la operación se confirma
- **THEN** versión y binario existen juntos

### Requirement: Guardar y leer sin sobrescribir
`DatabaseStorage.save` SHALL insertar el binario con su tamaño y SHA-256, y SHALL fallar con `StorageError` si la referencia ya existe sin modificar el contenido existente. `read` SHALL devolver exactamente los bytes guardados y SHALL fallar con `StorageError` si la referencia no existe. Las referencias SHALL validarse como las del almacén de archivos (sin rutas fuera de la raíz).

#### Scenario: Ida y vuelta
- **WHEN** se guarda y se lee un PDF
- **THEN** los bytes son idénticos

#### Scenario: Referencia repetida
- **WHEN** se guarda dos veces la misma referencia
- **THEN** la segunda falla y el contenido original no cambia

#### Scenario: Inexistente
- **WHEN** se lee una referencia que no existe
- **THEN** falla con `StorageError`

### Requirement: Integridad al leer
`read` SHALL recalcular el SHA-256 del contenido y compararlo con el guardado, y SHALL fallar con `StorageError` si no coinciden.

#### Scenario: Contenido alterado en la base
- **WHEN** alguien modifica el contenido de un binario saltando las protecciones (por ejemplo, tras quitar el trigger)
- **THEN** la lectura falla y `verify` del documento informa que el binario no está disponible o no coincide

### Requirement: Inmutabilidad a nivel de base de datos
La base de datos SHALL rechazar todo `UPDATE` sobre `stored_blob` y todo `DELETE` salvo el de referencias que comienzan con `prepared/` (estado intermedio de la firma, descartable). `delete_prepared` SHALL ser la única forma de borrar y SHALL rechazar referencias que no comiencen con `prepared/`.

#### Scenario: Modificar un binario de versión
- **WHEN** se intenta un `UPDATE` o un `DELETE` sobre el binario de una versión
- **THEN** la base de datos lo rechaza explícitamente

#### Scenario: Descartar el estado intermedio
- **WHEN** termina una firma
- **THEN** los binarios `prepared/…` correspondientes se eliminan y los de las versiones permanecen

### Requirement: Migración entre almacenes
`python -m firmadoc.storage_migrate files-to-database` SHALL copiar a `stored_blob` los binarios de las versiones registradas que existen como archivos, verificando cada uno contra el `document_hash` de su versión (los que no coinciden o faltan se informan y no se copian), SHALL ser idempotente (los ya copiados e idénticos se omiten; uno existente con contenido distinto se informa como conflicto) y SHALL NOT borrar el origen. `database-to-files` SHALL hacer lo inverso con las mismas garantías, sin sobrescribir archivos.

#### Scenario: Migración completa
- **WHEN** hay versiones con archivos y se ejecuta `files-to-database`
- **THEN** cada binario queda en la base, `verify` de cada documento da el mismo resultado que antes y el resumen informa cuántos se copiaron

#### Scenario: Repetir
- **WHEN** se ejecuta de nuevo
- **THEN** no copia nada y no falla

#### Scenario: Archivo corrupto o ausente
- **WHEN** un archivo no coincide con el hash de su versión o no existe
- **THEN** se informa, no se copia y el comando termina con código distinto de cero

#### Scenario: Inversa
- **WHEN** se ejecuta `database-to-files`
- **THEN** los binarios de las versiones aparecen como archivos con el contenido verificado, sin pisar los existentes
