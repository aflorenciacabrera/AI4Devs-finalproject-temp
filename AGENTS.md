---
description: Reglas de desarrollo de Firmadoc, aplicables a todos los agentes de IA (Claude Code, Cursor, Codex, Gemini).
alwaysApply: true
---

## 1. Contexto del proyecto

**Firmadoc** es un servicio de firma digital institucional, embebible en otros sistemas (trabajo final del Master AI4Devs). La fuente de verdad del diseño es `README.md` (secciones 1 a 7); las especificaciones vigentes están en `openspec/specs/`.

| Área | Carpeta | Stack | Verificación |
|------|---------|-------|--------------|
| API | `backend/src/firmadoc/` | Python 3.11+, FastAPI, SQLAlchemy 2 + Alembic, pyHanko (PAdES, firma diferida), pydantic-settings | `ruff check .` · `pytest tests` |
| Agente local | `agent/src/firmadoc_agent/` | Python, python-pkcs11, diálogo tkinter, PyInstaller | `ruff check agent` · `pytest agent/tests` (SoftHSM en CI) |
| Widget de firma | `widget/` | React 19 + TypeScript (Vite), Vitest + Testing Library + axe | `npm run typecheck && npm run lint && npm test && npm run build` |
| Panel de administración | `frontend/` | Angular 21 (standalone, zoneless, sin enrutador), PrimeNG 21, Vitest | `npm test && npm run build` |
| End-to-end | `tests/e2e/` | pytest + Chrome real (servidor, agente y página anfitriona en otro origen) | `pytest tests/e2e` |

- **Backlog**: Jira, proyecto `FIRDOC`. Cada change de OpenSpec cita la clave `FIRDOC-N` que implementa.
- **Idioma**: documentación, specs, commits y textos de interfaz en español (rioplatense en el widget); identificadores de código, endpoints y nombres de archivos en inglés.
- **Confidencialidad**: no nombrar al organismo empleador, la provincia ni al proveedor comercial de referencia en código, docs ni commits.

## 2. Principios

- **Tareas chicas, de a una**: incrementos enfocados; no adelantarse a tareas que todavía no están en `tasks.md`.
- **Tests primero cuando sea posible**: toda tarea de seguridad (desafíos, validación de confianza, agente, orígenes, tokens) lleva su test.
- **Tipado completo**: TypeScript estricto en `widget/` y `frontend/`; type hints en Python.
- **Reutilizar patrones**: proveedores (`providers/base.py`), servicios (`services/`), pantallas del widget (`screens/`), secciones del panel (`sections/`) antes de crear abstracciones nuevas.
- **Alcance mínimo**: no tocar código no relacionado; diffs chicos y revisables.
- **PrimeNG antes que CSS a medida** en el panel: agotar `severity`, `styleClass`, pass-through `[pt]` y tokens del tema antes de escribir CSS propio (y comentar por qué). En el widget los estilos viven en `widget/src/styles/` con sus tokens.
- **Pedir permiso antes de agregar dependencias**: nunca `pip install`, `npm install <paquete>` ni cambios en `pyproject.toml`, `agent/pyproject.toml`, `widget/package.json` o `frontend/package.json` sin confirmación explícita. PrimeNG se queda en la 21 (la 22 cambia de licencia).
- **Desarrollar contra SoftHSM o el token de software** (`make agent`) antes de usar un token físico.

### Invariantes del dominio (no se negocian)

- `DocumentVersion` y `AuditEvent` son **append-only**: sin `UPDATE`/`DELETE`, ni migraciones destructivas.
- Toda firma completada genera una **nueva versión vigente** y queda **descargable**; nunca son alternativas.
- Los **desafíos de firma son de un solo uso**, con vencimiento, atados a la solicitud y a la sesión.
- **Firma diferida**: el PDF nunca viaja a la PC; la clave privada nunca toca el servidor; el **PIN se ingresa solo en el agente** y nunca se registra ni se reintenta.
- La **API key del integrador nunca llega al navegador**; el widget usa el token acotado del fragmento `#t=`, que vive solo en memoria.
- `postMessage` siempre con `targetOrigin` explícito (nunca `"*"`) y validación del emisor; `frame-ancestors` por integrador.
- El agente escucha solo en `127.0.0.1`, acepta solo `allowed_origins`, expone dos operaciones (listar certificados, firmar hashes) y confirma con el nombre del documento antes de firmar.
- Panel: CSP estricta con nonce por pedido; sin `innerHTML`; el único `bypass` del sanitizador es el `src` del iframe con la `signing_url` del backend.

## 3. Idioma

- Español para documentación (`docs/`, `README.md`, specs, proposals, tasks), mensajes de commit, textos de interfaz y comentarios que expliquen decisiones.
- Inglés para identificadores, endpoints, nombres de archivos, claves de configuración y códigos de error de la API (`errors.py`).

## 4. Documentación de referencia

- [README.md](./README.md): §1 producto, §2 arquitectura y §2.5 seguridad, §3 modelo de datos, §4 API, §5 historias de usuario, §6 tickets.
- [docs/](./docs/): `admin.md`, `agent-contract.md`, `database.md`, `demo.md`, `documents-api.md`, `firmar.md`, `real-mode.md`, `signature-batches.md`, `timestamping.md`, `webhooks.md`; `prototipo-referencia-firmadoc.md` y `design/mockup/` como referencia visual.
- [docs/documentation-standards.md](./docs/documentation-standards.md): qué documento se actualiza con cada tipo de cambio.
- READMEs de cada subproyecto: `backend/README.md`, `agent/README.md`, `widget/README.md`, `frontend/README.md`.
- `prompts.md`: registro del uso de IA (formato oficial de la entrega); se actualiza cuando una fase nueva usa prompts relevantes.

## 5. Skills y agentes del proyecto

- Los skills viven en `ai-specs/skills/` y los agentes en `ai-specs/agents/`; se copian a `.claude/` y `.cursor/`.
- Cuando un pedido coincide con la descripción de un skill, cargar y seguir su `SKILL.md` antes de continuar.
- **Agentes** (planifican, no implementan; dejan el plan en `.claude/doc/<feature>/`):
  - `backend-developer`: `backend/` y `agent/` (API, proveedores, PAdES, validación de confianza, agente PKCS#11).
  - `frontend-developer`: `frontend/` (panel Angular + PrimeNG) y `widget/` (React).
- **Skills**:
  - `security-audit`: auditoría de seguridad con checklist propio de Firmadoc (OWASP Top 10 adaptado a PKI, agente local, CSP y webhooks). **Obligatorio** antes de archivar cambios que toquen autenticación, validación de confianza, desafíos, el agente, orígenes/CSP, almacenamiento de claves o webhooks.
  - `adversarial-review`: revisión adversarial en otra sesión o agente antes de archivar.
  - `code-auditing`: auditoría de calidad, deuda técnica y código muerto.
  - `commit`: commits y pull requests según el estilo del repositorio.
  - `enrich-us`: enriquecer historias del backlog `FIRDOC` en Jira.
  - `show-spec-working`: demostrar una spec en vivo con `make demo`, el navegador y `curl`.
  - `update-docs`: actualizar la documentación afectada por un cambio.
  - `sync-agent-symlinks`: re-sincronizar las copias de `ai-specs/` en `.claude/` y `.cursor/`.
  - `using-git-worktrees`, `writing-skills`, `explain`, `meta-prompt`: utilitarios genéricos.
- Los skills y comandos de OpenSpec (`openspec-*`, `/opsx:*`) los genera la CLI de OpenSpec; no se editan a mano ni se copian desde `ai-specs/`.

## 6. Portabilidad multiagente

- **Fuente canónica**: `ai-specs/`. `AGENTS.md` lleva las reglas; `CLAUDE.md` es una copia idéntica para Claude Code.
- **Windows**: se usan copias de archivos, no symlinks (requieren permisos elevados). Tras editar un skill o agente en `ai-specs/`, re-sincronizar `.claude/skills`, `.claude/agents`, `.cursor/skills` y `.cursor/agents` (skill `sync-agent-symlinks`).

## 7. Flujo OpenSpec

Leer `openspec/config.yaml` antes de redactar o editar cualquier artefacto de OpenSpec.

Flujo recomendado (Claude Code usa `/opsx:<verbo>`, Cursor `/opsx-<verbo>`, Codex el skill `openspec-*` equivalente):

1. `/opsx:propose "descripción"`: crea la carpeta del change con proposal, deltas de specs, design y tasks (citando `FIRDOC-N`).
2. `/opsx:apply`: implementa las tareas de a una.
3. `/opsx:verify`: comprueba que la implementación cumple los artefactos.
4. `/opsx:sync`: vuelca los deltas a `openspec/specs/`.
5. `/opsx:archive`: archiva el change.
6. Opcionales: `/opsx:explore` para pensar una idea antes de proponerla; `/opsx:update` para revisar un change en curso.

### Estructura obligatoria de las tareas

1. Revisar las specs vigentes de la capacidad afectada en `openspec/specs/`.
2. Agregar o actualizar tests del área tocada (`tests/`, `agent/tests/`, `widget/tests/`, `*.spec.ts` del panel). Las tareas de seguridad siempre llevan test.
3. Ejecutar la verificación del área (tabla de §1) y `ruff` en Python.
4. Verificación manual con `make demo` para cambios de interfaz o de flujo (el agente la ejecuta cuando puede).
5. Actualizar `docs/`, el README del subproyecto o `README.md` cuando cambian convenciones, API o arquitectura.
6. Tareas de hasta 2 horas.

### Condición de cierre

- No marcar una tarea como completa hasta que los tests pasen y la documentación esté actualizada.
- Si el alcance cambia después de `/opsx:apply`, actualizar los artefactos de OpenSpec antes de seguir codificando.
- Antes de archivar un cambio sensible (ver §5), correr `security-audit` y, de ser posible, `adversarial-review` en otra sesión.
