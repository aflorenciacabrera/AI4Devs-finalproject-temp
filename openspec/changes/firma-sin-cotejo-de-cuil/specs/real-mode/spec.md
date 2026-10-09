## ADDED Requirements

### Requirement: Advertencia por firma sin cotejo de CUIL
La verificación previa (`python -m firmadoc.preflight`) SHALL informar como **advertencia** (`cuil_match_disabled`), tanto en modo real como fuera de él, que el cotejo del CUIL del certificado con el firmante está desactivado (`FIRMADOC_REQUIRE_CUIL_MATCH=false`), indicando que cualquier titular de un certificado válido puede firmar una solicitud cuyo enlace posea y cómo activarlo. Con el cotejo activado SHALL informarlo como dato informativo.

#### Scenario: Modo real sin cotejo
- **WHEN** `FIRMADOC_REAL_MODE=true` y `FIRMADOC_REQUIRE_CUIL_MATCH` no está definida o es `false`
- **THEN** el preflight muestra la advertencia `cuil_match_disabled` y, si no hay errores, el código de salida es 0

#### Scenario: Cotejo activado
- **WHEN** `FIRMADOC_REQUIRE_CUIL_MATCH=true`
- **THEN** el preflight no muestra la advertencia y lo informa como dato
