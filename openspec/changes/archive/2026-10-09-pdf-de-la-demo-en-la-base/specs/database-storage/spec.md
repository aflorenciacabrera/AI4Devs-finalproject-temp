## MODIFIED Requirements

### Requirement: Migración entre almacenes
`python -m firmadoc.storage_migrate files-to-database` SHALL copiar a `stored_blob` los binarios de las versiones registradas que existen como archivos, verificando cada uno contra el `document_hash` de su versión (los que no coinciden o faltan se informan y no se copian), SHALL ser idempotente (los ya copiados e idénticos se omiten; uno existente con contenido distinto se informa como conflicto) y SHALL NOT borrar el origen. Una versión cuyo binario ya está en el destino y no existe en el origen (creada directamente en el destino) SHALL omitirse sin informarse como problema. `database-to-files` SHALL hacer lo inverso con las mismas garantías, sin sobrescribir archivos.

#### Scenario: Migración completa
- **WHEN** hay versiones con archivos y se ejecuta `files-to-database`
- **THEN** cada binario queda en la base, `verify` de cada documento da el mismo resultado que antes y el resumen informa cuántos se copiaron

#### Scenario: Repetir
- **WHEN** se ejecuta de nuevo
- **THEN** no copia nada y no falla

#### Scenario: Archivo corrupto o ausente
- **WHEN** un archivo no coincide con el hash de su versión o no existe, y el binario tampoco está en el destino
- **THEN** se informa, no se copia y el comando termina con código distinto de cero

#### Scenario: Versión creada en el destino
- **WHEN** una versión tiene su binario en `stored_blob` y ningún archivo en el origen
- **THEN** se omite y el comando no la informa como problema

#### Scenario: Inversa
- **WHEN** se ejecuta `database-to-files`
- **THEN** los binarios de las versiones aparecen como archivos con el contenido verificado, sin pisar los existentes
