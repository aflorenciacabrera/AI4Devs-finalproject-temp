## ADDED Requirements

### Requirement: Alta de integradores
`python -m firmadoc.integrators create --name <nombre> --origin <origen>…` SHALL crear un `IntegratingSystem` con una API key y un secreto de webhook generados con un generador criptográficamente seguro, SHALL mostrarlos **una sola vez** y SHALL guardar únicamente el hash SHA-256 de la API key.

#### Scenario: Creación
- **WHEN** se ejecuta el comando de alta con un nombre y un origen
- **THEN** se imprime la API key y el secreto de webhook, y en la base solo existe el hash de la API key

#### Scenario: Orígenes inválidos
- **WHEN** un origen no tiene el formato `esquema://host[:puerto]` exacto
- **THEN** el comando falla sin crear el integrador

#### Scenario: Nombre repetido
- **WHEN** ya existe un integrador con ese nombre
- **THEN** el comando falla indicando el conflicto

### Requirement: Rotación del secreto de webhook
`python -m firmadoc.integrators rotate-webhook-secret --name <nombre>` SHALL reemplazar el secreto de ese integrador por uno nuevo, mostrarlo una sola vez y registrar la rotación en el registro del servidor, sin tocar su API key.

#### Scenario: Rotación
- **WHEN** se rota el secreto
- **THEN** las entregas nuevas se firman con el secreto nuevo y la API key sigue valiendo

### Requirement: Listado sin secretos
`python -m firmadoc.integrators list` SHALL mostrar los integradores (nombre, orígenes, fecha de alta, si tienen secreto de webhook) sin mostrar nunca la API key, su hash ni el secreto.

#### Scenario: Listado
- **WHEN** se ejecuta el listado
- **THEN** ninguna línea contiene una API key, un hash ni un secreto
