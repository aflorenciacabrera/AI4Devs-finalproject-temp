## Context

Ver `proposal.md` («Why»). Estado actual:

- `CertificateChecker.validate(der, expected_cuil)` hace todas las comprobaciones y, al final, `_check_cuil` (`403 cuil_mismatch`) solo si `expected_cuil` no es `None`. El único llamador que pasa un CUIL es `TokenAgentProvider` (`resolve_certificate` y `revalidate_certificate`), con `signer.identifier`.
- `ValidatedCertificate.cuil` ya se persiste en `Certificate.cuil` y se muestra en el panel y la verificación: la trazabilidad de quién firmó no depende del cotejo.
- El proveedor `firmar` coteja el CUIL en el callback (`remote_signing.py`) porque el servicio remoto deriva la firma por CUIL. No se toca.
- El widget tiene el mensaje de `cuil_mismatch`; sigue sirviendo con el cotejo activado.

## Goals / Non-Goals

**Goals:**
- Que, por defecto, firmar con token exija solo un certificado válido y el PIN en el agente.
- Un único interruptor explícito, documentado, para recuperar el cotejo donde haga falta.
- Que el operador vea en el preflight que el cotejo está apagado.

**Non-Goals:**
- Tocar el `CertificateChecker`: conserva `expected_cuil` y su test unitario, que prueban la capacidad.
- Cambiar el modelo de datos o el contrato del agente.

## Decisions

1. **Interruptor en `Settings` (`require_cuil_match: bool = False`, `FIRMADOC_REQUIRE_CUIL_MATCH`) y decisión en el proveedor `token`.** `TokenAgentProvider` recibe el booleano en el constructor (`_token(settings)` ya arma el proveedor con `Settings`) y pasa `signer.identifier` a `validate` solo si está activado; de lo contrario pasa `None`. Alternativa descartada: quitar `_check_cuil` del checker. Rompería el test unitario de la capacidad y dejaría sin camino a los integradores que sí necesitan el cotejo.

2. **Por defecto apagado, también en modo real.** Es lo que pidió la usuaria y es coherente con que el PIN sea el factor que identifica al firmante. El riesgo (quien posee el enlace de firma y un certificado válido cualquiera puede firmar) se hace visible en el preflight como advertencia `cuil_match_disabled` y en la documentación; no se convierte en error para no bloquear el modo real.

3. **La demo no cambia de código.** Con el cotejo apagado, `--cuil/--nombre` solo etiquetan al firmante del panel; se actualiza la documentación para decir que ya no hacen falta para firmar con el token físico y que la firma registra el titular real del certificado.

4. **Tests parametrizados por el interruptor.** Los casos `cuil_ajeno` y `sin_cuil` de `tests/test_token_flow.py` pasan a esperar `200` por defecto y `403 cuil_mismatch` con el interruptor activado (fixture que ajusta `Settings`). Igual en `test_widget_endpoints.py` y en el lote.

## Risks / Trade-offs

- [Un integrador que confiaba en el `403` para impedir que firme otra persona ahora recibe `200`] → cambio de comportamiento documentado en el README (sección de errores de la API) y en `.env.example`; la variable recupera el comportamiento. La firma registra siempre el certificado que firmó.
- [Solicitudes creadas con un firmante «A» firmadas con el certificado de «B»: la auditoría muestra ambos] → es el comportamiento buscado; el panel y `verify` ya exponen el sujeto del certificado.
- [El widget ya no verá `cuil_mismatch` por defecto; el mensaje queda sin usar en la mayoría de los despliegues] → se conserva: cuesta nada y sirve con el cotejo activado.

## Migration Plan

Sin migraciones. Quien quiera conservar el comportamiento anterior define `FIRMADOC_REQUIRE_CUIL_MATCH=true`. Rollback: revertir el commit.
