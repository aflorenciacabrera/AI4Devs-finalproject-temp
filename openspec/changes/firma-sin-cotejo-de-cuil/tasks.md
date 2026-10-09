## 1. Interruptor y proveedor token

- [x] 1.1 `config.py`: `require_cuil_match: bool = False` con comentario; `.env.example`: `# FIRMADOC_REQUIRE_CUIL_MATCH=false` explicado.
- [x] 1.2 `providers/token.py`: `TokenAgentProvider(checker, trust, require_cuil_match=False)`; `resolve_certificate` y `revalidate_certificate` pasan `signer.identifier` solo si está activado; `providers/__init__.py` lo construye con `settings.require_cuil_match`.
- [x] 1.3 `preflight.py`: advertencia `cuil_match_disabled` cuando está apagado (en modo real y fuera de él) y dato informativo cuando está activado.

## 2. Tests (validación de confianza: cada caso con su test)

- [x] 2.1 `tests/test_token_flow.py`: `cuil_ajeno` y `sin_cuil` esperan `200` por defecto y el certificado registrado lleva el CUIL del certificado (o ninguno); nuevo test parametrizado con `FIRMADOC_REQUIRE_CUIL_MATCH=true` que espera `403 cuil_mismatch` para ambos casos sin crear desafío.
- [x] 2.2 `tests/test_widget_endpoints.py`: `test_cuil_distinto_mismo_codigo` pasa a cubrir ambos valores del interruptor (por defecto `200`; activado `403 cuil_mismatch`).
- [x] 2.3 `tests/test_signature_batches.py`: si hay un caso de CUIL distinto, ajustarlo igual; si no, agregar uno con el interruptor activado.
- [x] 2.4 Test del preflight (`tests/test_real_mode.py` o el que cubra `preflight`): advertencia `cuil_match_disabled` por defecto y ausente con el interruptor activado.
- [x] 2.5 `pytest tests -q --ignore=tests/e2e` y `ruff check` en verde.

## 3. Documentación

- [x] 3.1 `README.md`: fila «Certificado rechazado antes del PIN» (quitar «de otra persona (CUIL distinto)» salvo con el interruptor), errores de la API (`403` solo con `FIRMADOC_REQUIRE_CUIL_MATCH=true`), fila «Firma con el token físico» (ya no hace falta `--cuil`).
- [x] 3.2 `docs/agent-contract.md` (tabla de códigos: `cuil_mismatch` solo con el cotejo activado), `docs/demo.md` (paso 4: `--cuil/--nombre` opcionales, solo etiquetan al firmante del panel), `docs/real-mode.md` (sección Confianza: el CUIL ya no se exige; cómo activarlo).

## 4. Verificación con el token físico

- [ ] 4.1 Reiniciar la demo sin `--cuil` y comprobar que el panel permite firmar con el token físico pidiendo solo el PIN (lo ejecuta la titular del token).
