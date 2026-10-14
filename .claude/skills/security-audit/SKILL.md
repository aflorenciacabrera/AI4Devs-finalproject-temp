---
name: security-audit
description: Usar cuando se pide una auditoría de seguridad, revisión de seguridad, chequeo OWASP Top 10, análisis de vulnerabilidades o cierre de un cambio sensible de Firmadoc (autenticación, validación de confianza, desafíos de firma, agente local, CSP/orígenes, tokens, almacenamiento de claves, webhooks). Cubre backend/ (FastAPI), agent/ (PKCS#11), widget/ (React) y frontend/ (Angular).
author: Firmadoc (adaptado del skill owasp-security-audit)
version: 1.0.0
---

# Auditoría de seguridad de Firmadoc

Metodología para auditar Firmadoc contra el OWASP Top 10:2021 **más el modelo de amenazas propio del producto**: firma diferida con token criptográfico, agente local en `127.0.0.1`, widget embebido en sistemas de terceros, validación PKI en el servidor y auditoría append-only.

**Principio:** cada hallazgo se demuestra con herramienta o con evidencia en el código (archivo y línea), se prioriza por explotabilidad y viene con una corrección concreta y su test.

## Cuándo usar

- Pedido explícito de auditoría o revisión de seguridad.
- **Antes de archivar** un change de OpenSpec que toque: `api/deps.py`, `signing_token.py`, `certificate_validation.py`, `trust.py`, `services/signature_flow.py`, `services/widget*.py`, `providers/`, `webhooks.py`, `integrators.py`, `storage.py`, la CSP en `main.py`/`frontend_pages.py`/`pages.py`, `agent/src/firmadoc_agent/server.py`/`config.py`, `widget/src/embed/`, `widget/src/bootstrap/`, `frontend/src/app/core/admin-api.ts` o `widget-messages.ts`.
- Antes de habilitar `FIRMADOC_REAL_MODE=true` en un despliegue.
- Triage de vulnerabilidades en dependencias.

**Cuándo no usar:** corregir una vulnerabilidad única ya conocida (corregirla y testearla), revisión de calidad general (`code-auditing`), seguridad de infraestructura o red (fuera de alcance; acá se audita la aplicación).

## Alcance y lectura previa

1. `AGENTS.md` §2 (invariantes del dominio) y `README.md` §2.5 (seguridad) y §2.6 (tests de rechazo esperados).
2. `docs/agent-contract.md`, `docs/webhooks.md`, `docs/real-mode.md`, `widget/README.md` (mensajes y orígenes), `frontend/README.md` (CSP y nonce).
3. Specs vigentes: `openspec/specs/certificate-validation`, `trust-management`, `signature-requests`, `widget-session`, `widget-embedding`, `agent-local-api`, `agent-token-signing`, `integrator-management`, `webhook-delivery`, `real-mode`.
4. Si se audita un change concreto: su `proposal.md`, `design.md`, deltas y `tasks.md`.

## Fase 0: entorno y escaneos automáticos

Correr todo primero; dejan el piso antes de la revisión manual.

| Herramienta | Comando | Cubre |
|-------------|---------|-------|
| pip-audit | `pip install pip-audit && pip-audit` (raíz y `agent/`) | A06: CVE en dependencias Python |
| npm audit | `cd widget && npm audit --json`; `cd frontend && npm audit --json` | A06: CVE en dependencias JS |
| ruff | `ruff check .` (incluye reglas bugbear) | A03/A05: errores de código |
| ESLint | `cd widget && npm run lint` | A03/A08 en el widget |
| Secretos en código | `rg -n -i '(password\|secret\|api[_-]?key\|token\|pin)\s*[:=]\s*["\x27][^"\x27]{8,}' --glob '!node_modules' --glob '!*.lock' --glob '!package-lock.json'` | A02: secretos hardcodeados |
| Secretos en el historial | `git log --all --diff-filter=A --name-only -- '*.env' '*.key' '*.pem' '*.p12' '*.pfx' 'tests/pki/out/*'` | A02: secretos commiteados |
| `.gitignore` | Verificar `.env`, `*.key`, `backend/trust/*.key`, `tests/pki/out/`, `data/`, `*.db` | A02 |
| Claves de prueba | `rg -n 'BEGIN (RSA |EC )?PRIVATE KEY' --glob '!node_modules'` | A02: solo material de prueba generado por `tests/pki.py` o `demo_pki.py` |
| HTML peligroso | `rg -n 'innerHTML\|dangerouslySetInnerHTML\|bypassSecurityTrust' frontend/src widget/src` | A03/A08 |
| postMessage sin origen | `rg -n 'postMessage\(' widget/src frontend/src` y comprobar que ningún `targetOrigin` sea `"*"` | A01/A05 |
| Salidas a la red | `rg -n 'httpx\.\|requests\.\|urlopen' backend/src agent/src` | A10 |
| PIN en logs | `rg -n -i 'pin' agent/src/firmadoc_agent/logs.py agent/src/firmadoc_agent/*.py backend/src` y verificar que nunca se registre ni viaje al servidor | Específico |

**Registrar la línea base:** vulnerabilidades por severidad, dependencias desactualizadas, hits del escaneo de secretos (los esperados: `tests/pki.py`, `demo_pki.py`, `data/demo/` ignorado por git).

Nota: `127.0.0.1:47123` en `widget/src/api/agentClient.ts` y en `FIRMADOC_AGENT_URL` **es legítimo** (es el agente local); no es un endpoint de depuración.

## Fase 1: auditoría por categoría

Auditar **todas** las categorías; si una no aplica, dejar "N/A" con justificación. Para cada una: correr los chequeos, registrar hallazgos con archivo y línea, y anotar qué se revisó aunque esté limpio.

### A01: Control de acceso

**Paso 1: enumerar las rutas.** `rg -n '@router\.(get|post|put|patch|delete)' backend/src/firmadoc/api` y, para cada una, verificar la dependencia de autenticación en `api/deps.py`.

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| Toda ruta de `/api/v1` exige API key del integrador | `Depends` de `deps.py` en cada endpoint de `routes.py` | Crítica |
| Alcance por integrador | Solicitudes, documentos, versiones y descargas filtradas por `integrator_id`; probar acceso cruzado (IDOR) con dos integradores | Crítica |
| Endpoints del widget solo con token acotado | `widget_routes.py`, `widget_batch_routes.py`: token HMAC válido, no vencido y de **esa** solicitud o lote | Crítica |
| Administración solo con `admin_token` | `admin_routes.py`, `admin_pages.py`, `frontend_pages.py`; sin token configurado, 404 | Crítica |
| Callback de firma remota autenticado | `firmar_routes.py`: HMAC con `firmar_callback_secret` | Alta |
| `frame-ancestors` por integrador | `pages.py`: lista explícita de `allowed_origins`; nunca `*` | Alta |
| Agente: `allowed_origins` | `agent/.../server.py`: `Origin` validado en preflight y en la petición; `127.0.0.1` solamente | Crítica |
| Panel: 401 cierra sesión | `admin-api.ts` | Media |

### A02: Fallas criptográficas

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| API keys hasheadas en reposo y mostradas una sola vez | `integrators.py`, `services/integrator_admin.py`, `integrators.ts` | Crítica |
| `signing_secret` y `admin_token` con mínimo 32 caracteres y obligatorios en `real_mode` | `config.py`, `preflight.py`, `docs/real-mode.md` | Crítica |
| Token del widget: HMAC, TTL (`signing_token_ttl_seconds`), acotado a la solicitud, en el fragmento `#t=` | `signing_token.py`, `widget/src/bootstrap/token.ts` (borra barra e historial) | Alta |
| Clave del proveedor `local` cifrada o fuera del repo | `providers/local.py`, `local_cert_dir`; `real_mode` rechaza certificados de demostración | Alta |
| Anclas de confianza con procedencia verificada | `backend/trust/`, `trust.py`; huella SHA-256 documentada | Alta |
| Algoritmos: SHA-256 o superior, RSA ≥ 2048 / ECDSA; sin SHA-1/MD5 | `pdf_engine.py`, `certificate_validation.py`, `agent/.../pkcs11_backend.py` | Alta |
| TLS obligatorio para API, widget, callbacks y webhooks | `webhook_allow_http=false` en producción; `public_base_url` https | Alta |
| Sin secretos en el repo ni en el historial | Fase 0 | Crítica |

### A03: Inyección

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| Sin SQL crudo | `rg -n 'text\(\|execute\("' backend/src` → solo SQLAlchemy parametrizado | Crítica |
| Validación del PDF de entrada | tipo (`%PDF-`), `max_document_bytes`, sin ejecutar JavaScript/XFA; `services/documents.py`, `panel_upload.py` | Alta |
| Nombre de archivo seguro | `filenames.py`: sin rutas, sin caracteres de control; descarga con `Content-Disposition` escapado | Alta |
| Path traversal en almacenamiento | `storage.py`: rutas derivadas de ids, nunca del nombre original | Alta |
| Sin `eval`/`exec`/`subprocess` con entrada externa | `rg -n 'eval\(\|exec\(\|subprocess' backend/src agent/src` | Crítica |
| Listas blancas en filtros y orden | `services/admin.py`, `documents.py`: campos de orden/filtro validados | Media |
| Sin interpolación de entrada en logs | Revisar `logging` con datos del usuario | Baja |
| Pydantic con `extra="forbid"` o campos explícitos | `api/schemas.py`; nada de volcar el body en el modelo | Alta |

### A04: Diseño inseguro

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| Desafío de un solo uso | `signature_flow.py`: consumido al completar; segundo `complete` → rechazo | Crítica |
| Desafío con vencimiento y sesión | `challenge_ttl_seconds`; `X-Session-Ref` igual en `prepare` y `complete` | Crítica |
| El hash firmado corresponde al desafío | Verificación de la firma contra el hash y el certificado elegido antes de incrustar | Crítica |
| Lote: fallo parcial no deja estados inconsistentes | `services/signature_batch.py`, `widget_batch.py`; `max_batch_size` | Alta |
| Límites de tamaño de cuerpo y de lote | `max_document_bytes`, `max_batch_size` | Media |
| Rate limiting por integrador y por token del widget | Verificar existencia y configuración; si falta, hallazgo Alto | Alta |
| Errores sin detalles internos | `errors.py`: `code` estable + mensaje; sin trazas ni rutas | Media |
| `real_mode` impide configuración insegura | `preflight.py`, `docs/real-mode.md` | Alta |

### A05: Configuración de seguridad

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| CSP del widget | `pages.py`: `default-src 'none'`, `connect-src` con la API y `agent_url`, `frame-ancestors` por integrador, sin `unsafe-inline` | Alta |
| CSP del panel | `frontend_pages.py`: nonce por pedido en `style-src`/`script-src`; `inlineCritical: false`; `providePrimeNG({ csp: { nonce } })` | Alta |
| Cabeceras: `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options` donde no se embebe, HSTS en producción | `main.py` middleware | Media |
| CORS | Sin `*`; solo orígenes de `panel_origins` y de los integradores | Alta |
| Sin modo debug ni documentación automática expuesta en producción | `main.py`: `/docs` y `/redoc` según `real_mode` | Media |
| Credenciales de demostración solo en demo | `seed.py`, `demo.py`: `firmadoc-demo-key` nunca en `real_mode` | Alta |
| Variables obligatorias validadas al arrancar | `preflight.py` | Media |
| Iframe del panel con `sandbox` mínimo y `referrerpolicy="no-referrer"` | `widget-dialog.ts` | Media |
| Agente: puerto fijo y configuración validada | `agent/.../config.py` rechaza claves desconocidas y puertos fuera de rango | Media |

### A06: Componentes vulnerables o desactualizados

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| `pip-audit` y `npm audit` sin críticas/altas | Fase 0 | Variable |
| Lockfiles commiteados | `widget/package-lock.json`, `frontend/package-lock.json` | Media |
| pyHanko, cryptography y pyhanko-certvalidator con versión mínima vigente | `pyproject.toml` | Media |
| PrimeNG fijado en 21 (cambio de licencia en 22) | `frontend/package.json` | Baja |
| PyInstaller del agente con versión reciente y binario reproducible | `agent/pyproject.toml`, `agent/packaging/` | Media |
| Scripts `postinstall` sospechosos | `rg '"(pre|post)install"' widget/node_modules/*/package.json frontend/node_modules/*/package.json` | Media |

### A07: Identificación y autenticación

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| Comparaciones de secretos en tiempo constante | `hmac.compare_digest` en `deps.py`, `signing_token.py`, `firmar_routes.py` | Alta |
| Rotación de API keys y deshabilitación de integradores | `services/integrator_admin.py` | Media |
| Token de administración en `sessionStorage`, no en URL ni `localStorage` | `admin-api.ts` | Media |
| Vinculación de identidad: CUIL del certificado vs. firmante (`require_cuil_match`) | `certificate_validation.py`; documentar el riesgo si está en `false` | Alta |
| PIN: solo en el agente, nunca reintentado, nunca persistido | `agent/.../ui_tk.py`, `service.py`, `pkcs11_backend.py` | Crítica |
| Cadena de confianza completa: anclas, vigencia, revocación (`revocation_mode`), uso de clave | `certificate_validation.py`; `hard-fail` en `real_mode` | Crítica |

### A08: Integridad de software y datos

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| Firmas incrementales: una firma nueva no invalida las anteriores | `pdf_engine.py` + test con dos firmas sucesivas | Alta |
| Verificación independiente del PDF firmado | Test con herramienta ajena a pyHanko (`pdfsig`) cuando esté disponible | Media |
| Webhooks firmados o con secreto por integrador | `webhooks.py`, `docs/webhooks.md` | Alta |
| Mensajes del widget al anfitrión sin token, PIN ni PDF | `embed/hostMessages.ts`, `widget/tests/sensitive.test.tsx` | Alta |
| Mensajes entrantes validados por ventana y origen | `frontend/src/app/core/widget-messages.ts`, `embed/widgetElement.ts` | Alta |
| Sin `innerHTML`/`dangerouslySetInnerHTML` | Fase 0 | Alta |
| Distribución del agente con huella publicada | `agent/packaging/`, `openspec/specs/agent-distribution` | Media |
| Sello de tiempo y revocación embebidos (B-LT) cuando hay TSA | `timestamping.py`; `tsa_required` en producción | Media |

### A09: Registro y monitoreo

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| `AuditEvent` y `DocumentVersion` sin `UPDATE`/`DELETE` | Modelos, migraciones y test de esquema (`tests/test_schema.py`) | Crítica |
| Auditoría registra quién, qué, cuándo y con qué certificado | `services/signature_flow.py` | Alta |
| Rechazos de validación y de autenticación registrados | 401/403, desafío inválido, certificado rechazado | Media |
| Nada sensible en logs: PIN, token, API key, PDF, clave | Backend y agente (`logs.py`) | Crítica |
| Entregas de webhook con historial y reintentos | `WebhookDelivery`, vista de auditoría del panel | Media |

### A10: SSRF

| Chequeo | Cómo | Severidad |
|---------|------|-----------|
| URL de webhook: `https`, sin hosts privados ni `localhost` salvo flags de desarrollo | `webhooks.py`: `webhook_allow_http`, `webhook_allow_private_hosts`; resolver DNS y rechazar rangos privados | Alta |
| CRL/OCSP: URLs tomadas del certificado (CDP/AIA) con timeout y sin seguir a hosts internos | `certificate_validation.py`, `revocation_fetch`, `crl_dir` como alternativa sin red | Alta |
| TSA y servicio de firma remota: URL solo de configuración, con timeout | `timestamping.py`, `providers/firmar.py` | Media |
| Sin redirecciones abiertas | `firmar_routes.py`, `pages.py` | Media |
| Rutas de archivo absolutas y derivadas de ids | `storage.py` | Media |

## Fase 1b: modelo de amenazas propio de Firmadoc

Además del Top 10, verificar explícitamente estos escenarios (cada uno debería tener un test en `tests/`, `agent/tests/` o `widget/tests/`):

| Escenario | Resultado esperado | Dónde |
|-----------|-------------------|-------|
| Reutilizar un desafío ya consumido | Rechazo | `tests/test_flow.py`, `test_token_flow.py` |
| Desafío vencido o de otra sesión (`X-Session-Ref` distinto) | Rechazo | idem |
| Firma hecha con otra clave que la del certificado elegido | Rechazo | `tests/test_signing_token.py`, `test_certificate_validation.py` |
| Certificado revocado, vencido, de otra AC o con CUIL distinto | Rechazo antes de pedir el PIN | `tests/test_certificate_validation.py` |
| Token del widget de otra solicitud o vencido | 401/403 | `tests/test_widget_endpoints.py` |
| Integrador A consulta documento de B | 404/403 | `tests/test_documents_api.py` |
| Página anfitriona fuera de `allowed_origins` | Navegador bloquea el iframe (`frame-ancestors`); agente rechaza `Origin` | `tests/e2e/`, `agent/tests/` |
| Petición al agente desde un origen no permitido | Rechazo en preflight y en la llamada | `agent/tests/` |
| Agente: hash recibido sin confirmación del usuario | No se firma | `agent/tests/` |
| Mensaje `postMessage` con token o PDF | Nunca ocurre | `widget/tests/sensitive.test.tsx` |
| `real_mode` con `signing_secret` vacío, `revocation_mode=off` o certificado de demostración | No arranca | `tests/test_real_mode.py` |
| Webhook a `http://` o a `10.0.0.1` en producción | Rechazo | `tests/test_webhooks.py` |

## Fase 2: clasificación

| Severidad | Criterio | Ejemplo en Firmadoc |
|-----------|----------|---------------------|
| **Crítica** | Explotable sin autenticación o rompe una invariante del dominio | Desafío reutilizable; endpoint sin API key; PIN registrado |
| **Alta** | Explotable con algo de esfuerzo o con impacto significativo | IDOR entre integradores; `frame-ancestors` abierto; webhook SSRF |
| **Media** | Requiere condiciones específicas | Cabecera faltante; dependencia desactualizada sin exploit conocido |
| **Baja** | Impacto mínimo | Mensaje de error demasiado verboso en desarrollo |

## Fase 3: plan de corrección

Para cada hallazgo: qué cambiar, dónde, ejemplo de código, **test que lo prueba** y cómo verificarlo. Agrupar:

- **Fase A, inmediata (< 1 día; críticas/altas)**: rotar secretos expuestos, cerrar endpoints, corregir desafíos, purgar secretos del historial.
- **Fase B, corto plazo (1 a 3 días)**: rate limiting, cabeceras, validaciones, logging.
- **Fase C, mediano plazo (1 a 2 semanas)**: dependencias, CI de seguridad, monitoreo.

Si la corrección excede un arreglo puntual, proponerla como change de OpenSpec (`/opsx:propose`) citando el `FIRDOC-N` correspondiente; por `openspec/config.yaml`, toda tarea de seguridad lleva su test.

## Fase 4: verificación en tiempo de ejecución

Con `make demo` (o `uvicorn firmadoc.main:app`) en `localhost:8000`:

```bash
# Cabeceras y CSP del widget y del panel
curl -sI http://localhost:8000/sign/00000000-0000-0000-0000-000000000000 | grep -iE 'content-security-policy|x-content-type|referrer-policy'
curl -sI http://localhost:8000/panel | grep -iE 'content-security-policy'

# API sin credenciales → 401
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/documents

# Administración sin token → 401/404
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/admin/documents

# Desafío reutilizado: segundo complete debe fallar (ID y API key de la demo)
H='X-API-Key: firmadoc-demo-key'
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/prepare -H "$H"
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/complete -H "$H"
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/complete -H "$H"   # esperado: rechazo

# Agente: origen no permitido → rechazo
curl -s -i -X OPTIONS http://127.0.0.1:47123/certificates -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: GET'

# Payload mayor que max_document_bytes → 413
python3 -c "print('x'*25000000)" | curl -s -X POST -H "$H" -H 'Content-Type: application/json' -d @- localhost:8000/api/v1/signature-requests -w "\n%{http_code}"
```

Enmascarar valores sensibles en el chat.

## Plantilla del informe

```markdown
# Auditoría de seguridad de Firmadoc

- **Alcance**: [change FIRDOC-N / módulo / todo el repo]
- **Fecha**: [AAAA-MM-DD]
- **Método**: análisis estático + herramientas + verificación en ejecución

## Escaneos automáticos
- pip-audit: críticas X | altas X | medias X | bajas X
- npm audit (widget / frontend): ...
- Secretos: X hallazgos (esperados: ...)

## Hallazgos por categoría
### A01: Control de acceso — [CRÍTICA/ALTA/MEDIA/BAJA/LIMPIO]
**Revisado:** ...
**Hallazgos:** [archivo:línea]
**Corrección:** [código + test]
[... A02 a A10 y modelo de amenazas propio ...]

## Matriz de prioridad
| Fase | Hallazgo | Severidad | Esfuerzo | Corrección |

## Verificación
- [ ] [hallazgo]: [cómo se verifica]

## Integración en CI (.github/workflows/ci.yml)
- [ ] `pip-audit` y `npm audit --audit-level=high` (fallar en críticas/altas)
- [ ] Escaneo de secretos (gitleaks)
- [ ] Tests de rechazo de la Fase 1b en la suite
```

Guardar el informe en `docs/security-audit-<fecha>.md` solo si el usuario lo pide; si no, entregarlo en el chat y resumir.

## Errores comunes

| Error | Por qué está mal | Corrección |
|-------|------------------|------------|
| Marcar "N/A" sin evidencia | Se asumió en lugar de verificar | Documentar qué se revisó |
| Auditar solo el backend | El widget cruza orígenes y el agente corre en la PC del usuario | Seguir el flujo de punta a punta: integrador → API → widget → agente → API → webhook |
| Confiar en que el ORM evita toda inyección | No cubre rutas, nombres de archivo ni logs | Revisar `filenames.py`, `storage.py` y logging |
| Tratar `127.0.0.1:47123` como endpoint de depuración | Es el agente local, parte del diseño | Verificar `allowed_origins` y el puerto, no su existencia |
| Hallazgos sin test | Se repiten en el próximo cambio | Cada corrección lleva su test de rechazo |
| Olvidar `real_mode` | Las configuraciones de demo son inseguras a propósito | Verificar que `preflight.py` las rechace en producción |
| Revisar solo el camino feliz del desafío | El riesgo está en reutilización, vencimiento y sesión cruzada | Probar los tres rechazos |
