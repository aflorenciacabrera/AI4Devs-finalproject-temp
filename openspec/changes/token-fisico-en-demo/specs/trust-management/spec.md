## ADDED Requirements

### Requirement: Anclas de la infraestructura de firma digital argentina incluidas en el repositorio
El directorio `backend/trust/` del repositorio SHALL incluir, en formato PEM y en archivos separados, el certificado de la **AC Raíz de la República Argentina** (emitido en 2016, autofirmado) y el de la **Autoridad Certificante de Firma Digital** de la ONTI (emitido por esa raíz en 2026). Su README SHALL documentar la huella SHA-256 de cada uno, la fuente oficial de la que se descargaron y cómo volver a verificarlas. Con ese directorio como `FIRMADOC_TRUST_DIR`, un certificado de firmante emitido por la AC de Firma Digital SHALL encadenar hasta la raíz sin configuración adicional.

#### Scenario: Anclas presentes
- **WHEN** se carga el directorio `backend/trust/` del repositorio
- **THEN** contiene exactamente una raíz, la AC Raíz de la República Argentina con huella SHA-256 `975c663546ed8923d132256f2f3300838e3fe01e04e37739e954ff931e9f8ba4`, y una intermedia, la Autoridad Certificante de Firma Digital con huella SHA-256 `b3c367a4e3842854c8820a9eda492318e2ca0ecf9abb8130de8f6dcd53ac2510`, y la intermedia está firmada por la raíz

#### Scenario: Cadena de un certificado emitido por la AC ONTI
- **WHEN** se valida, solo por cadena (sin revocación), un certificado de firmante emitido por la Autoridad Certificante de Firma Digital contra ese directorio
- **THEN** la cadena es de confianza

#### Scenario: Huellas documentadas
- **WHEN** se lee `backend/trust/README.md`
- **THEN** figuran ambas huellas SHA-256, la URL oficial de descarga de cada certificado y el comando para recalcular la huella
