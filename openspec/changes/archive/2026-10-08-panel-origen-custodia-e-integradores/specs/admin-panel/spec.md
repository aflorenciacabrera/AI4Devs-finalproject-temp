## ADDED Requirements

### Requirement: Navegación lateral y estilo
El panel SHALL ofrecer una barra lateral con las secciones «Firmar documento», «Documentos», «Auditoría», «Integradores» y «Confianza» (con la sección activa marcada y navegable con teclado), en lugar de pestañas. «Auditoría» SHALL reunir las entregas de webhook y los eventos de administración; «Confianza» SHALL reunir las anclas de confianza y el certificado propio. Se mantienen las reglas de seguridad de la página (CSP sin scripts ni estilos en línea, contenido como texto, token en `sessionStorage`) y el modo claro/oscuro.

#### Scenario: Cambiar de sección
- **WHEN** se elige «Integradores» en la barra lateral
- **THEN** se muestra esa sección y queda marcada como activa

#### Scenario: Secciones agrupadas
- **WHEN** se abre «Confianza»
- **THEN** se ven las anclas de confianza y el certificado propio

### Requirement: Listado de documentos
«Documentos» SHALL mostrar el listado con las columnas Documento (nombre y `vN`), Firmante, Fecha, Proveedor, Origen («Individual» o «Lote #…» con las filas de un lote contiguas), Estado en español con color (Firmado, Pendiente con su vencimiento, Firmando, Fallido) y Acciones; con búsqueda por documento o firmante y filtros por estado, proveedor, origen y fechas, y paginación.

#### Scenario: Origen y vencimiento
- **WHEN** hay un documento firmado en lote y uno pendiente con fecha límite
- **THEN** el primero muestra «Lote #…» y el segundo «Individual» con «Vence dd/mm/aaaa»

#### Scenario: Texto hostil
- **WHEN** un nombre de documento o firmante contiene HTML
- **THEN** se muestra como texto y no se ejecuta

### Requirement: Detalle del documento
Al elegir un documento SHALL mostrarse su detalle con «Volver a Documentos», nombre, ID externo, estado, descarga del firmado vigente, la **línea de tiempo** de la cadena de custodia (hora, actor, título y detalle), la tarjeta **Versiones** (la vigente marcada, con descarga de cada versión) y el **Detalle técnico**; sin mostrar IP de origen, hashes a firmar ni secretos.

#### Scenario: Ver la historia
- **WHEN** se abre el detalle de un documento firmado
- **THEN** se ve la línea de tiempo en orden, las versiones v1 y v2 con la v2 vigente y el detalle técnico

#### Scenario: Descargar una versión
- **WHEN** se elige «Descargar» en la v1
- **THEN** se baja el PDF original sin firmar

### Requirement: Pantalla de Integradores
«Integradores» SHALL listar los sistemas (nombre, orígenes permitidos, estado y si es interno) y permitir crear uno, editar sus orígenes, rotar su secreto de webhook, rotar su API key y deshabilitarlo o habilitarlo, con confirmación en las acciones que invalidan credenciales. La API key y el secreto en claro SHALL mostrarse una sola vez tras crear o rotar, con aviso de que no se vuelven a mostrar, y NO SHALL guardarse en el navegador. El sistema interno SHALL figurar sin acciones.

#### Scenario: Alta con credenciales de una sola vez
- **WHEN** se crea un integrador
- **THEN** se muestran su API key y su secreto de webhook con el aviso de guardarlos, y al volver al listado ya no aparecen

#### Scenario: Rotar con confirmación
- **WHEN** se elige «Rotar API key» y se cancela la confirmación
- **THEN** no se rota nada
