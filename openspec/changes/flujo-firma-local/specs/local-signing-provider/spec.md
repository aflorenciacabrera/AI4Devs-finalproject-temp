## ADDED Requirements

### Requirement: Interfaz común de proveedor
Los proveedores de firma SHALL implementar una interfaz común con las operaciones de preparar y completar, de modo que el flujo de `signature-requests` no dependa del proveedor concreto.

#### Scenario: Selección por proveedor
- **WHEN** una solicitud se crea con `provider: local`
- **THEN** el flujo usa el proveedor `local` sin cambios en el contrato de la API

### Requirement: Firma electrónica con certificado propio
El proveedor `local` SHALL firmar con un certificado autofirmado de demostración propio de Firmadoc, y las firmas resultantes SHALL ser PAdES de nivel B-B verificables por una herramienta independiente.

#### Scenario: Firma verificable
- **WHEN** se completa una solicitud `local`
- **THEN** el PDF resultante contiene una firma PAdES cuya integridad verifica con una herramienta independiente de la que la produjo

#### Scenario: Sin servicios externos
- **WHEN** no hay conectividad de red
- **THEN** el flujo `local` se completa de punta a punta

### Requirement: Firma sin intervención del cliente
Para `local`, `prepare` SHALL aceptar un cuerpo sin certificado y `complete` SHALL aceptar una lista de firmas vacía; en ese caso el servidor SHALL firmar el hash del desafío con su propia clave.

#### Scenario: Complete sin firmas
- **WHEN** se invoca `complete` con `signatures: []` sobre una solicitud `local` preparada
- **THEN** el servidor firma el hash del desafío vigente y completa la firma

### Requirement: Material criptográfico fuera del repositorio
La clave privada del certificado de demostración SHALL generarse en el primer uso en un directorio configurable, SHALL NOT versionarse y SHALL tener permisos restringidos al usuario del proceso cuando el sistema operativo lo permita.

#### Scenario: Primer uso
- **WHEN** no existe el certificado de demostración
- **THEN** se genera un par de claves y un certificado autofirmado, y se registra su `Certificate` con `provider: local`

#### Scenario: Reinicio del servicio
- **WHEN** el servicio se reinicia
- **THEN** reutiliza el mismo certificado sin crear uno nuevo
