## 1. Caché de CRL en el servidor

- [x] 1.1 `certificate_validation.py`: clase `CrlCache` (lock, `fresh(now)`, `add(crls)`, `clear()`), instancia de módulo `CRL_CACHE`; acepta bytes o `CertificateList`; registra en el log cada CRL nueva (emisor, `next_update`, bytes).
- [x] 1.2 `CertificateChecker`: `_context()` entrega `self.crls + CRL_CACHE.fresh(now)`; `_run()` conserva el contexto y alimenta la caché con `ctx.crls` cuando la consulta por red está habilitada, aun si la validación falla.

## 2. Tests (validación de confianza)

- [x] 2.1 `tests/test_certificate_validation.py`: fixture `autouse` que limpia `CRL_CACHE`; test «una validación alimenta la caché y la siguiente la aprovecha sin red» (certificado revocado rechazado por un checker sin CRL ni red); test «CRL vencida no se entrega» (`pki.ca.crl(next_update=pasado)` o equivalente); test «sin duplicados»; test «las CRL de `crl_dir` siguen aplicándose».
- [x] 2.2 `pytest tests/test_certificate_validation.py tests/test_token_flow.py tests/test_signature_batches.py -q` y `ruff check` en verde.

## 3. Documentación

- [x] 3.1 `docs/demo.md` (sección del token físico) y `docs/real-mode.md`: la primera validación de un certificado de una AC descarga su CRL (puede tardar); las siguientes la reutilizan en memoria hasta su `next_update`; con varios workers, cada proceso descarga la suya; `FIRMADOC_CRL_DIR` para compartir por disco.

## 4. Verificación con el token físico

- [ ] 4.1 Reiniciar la demo, firmar un documento y luego un lote de 4 con el token real: la segunda y siguientes validaciones tardan ~2 s (ver «CRL incorporada» una sola vez en el registro del servidor).
