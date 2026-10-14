# Estándares de documentación

Cómo se mantiene la documentación de Firmadoc y la capa de OpenSpec / `ai-specs/`.

## Mapa de documentos

| Documento | Propósito | Se actualiza cuando |
|-----------|-----------|---------------------|
| `README.md` | Fuente de verdad del diseño (formato oficial de la entrega): producto, arquitectura, seguridad, modelo de datos, API, historias, tickets, PRs | Cambia el alcance, la arquitectura, el modelo, un endpoint principal o se cierra un ticket/PR |
| `prompts.md` | Registro del uso de IA por fase | Una fase nueva usa prompts relevantes; se agregan agentes o skills al flujo |
| `AGENTS.md` / `CLAUDE.md` | Reglas para los agentes de IA (idénticos) | Cambian convenciones, invariantes, comandos de verificación o el flujo OpenSpec |
| `docs/documentation-standards.md` | Este archivo | Se agrega o renombra un documento |
| `docs/documents-api.md` | Endpoints de documentos y versiones | Cambia el contrato de `/api/v1/documents` |
| `docs/database.md` | Esquema, versionado, append-only, migraciones | Cambian `models.py` o las migraciones |
| `docs/agent-contract.md` | Contrato HTTP del agente local (origen, operaciones, errores) | Cambia `agent/src/firmadoc_agent/server.py` o `config.py` |
| `docs/admin.md` | Panel de administración y endpoints de admin | Cambian `admin_routes.py` o las secciones del panel |
| `docs/webhooks.md` | Entregas, reintentos, firma, SSRF | Cambia `webhooks.py` |
| `docs/signature-batches.md` | Firma en lote | Cambian `services/signature_batch.py` o `widget_batch.py` |
| `docs/timestamping.md` | Sello de tiempo (TSA) y niveles PAdES | Cambia `timestamping.py` o la configuración TSA |
| `docs/firmar.md` | Proveedor de firma remota y su simulador | Cambian `providers/firmar.py`, `mock_firmar.py` o `firmar_routes.py` |
| `docs/demo.md` | Modo demostración | Cambia `demo.py`, `seed.py` o el flujo de prueba |
| `docs/real-mode.md` | Requisitos de producción y `preflight` | Cambia `preflight.py` o una variable pasa a ser obligatoria |
| `docs/prototipo-referencia-firmadoc.md`, `design/mockup/` | Referencia visual | Se rediseña una pantalla |
| `docs/img/` | Capturas del producto real (`python docs/img/generar.py`) | Cambia el flujo visible |
| `backend/README.md`, `agent/README.md`, `widget/README.md`, `frontend/README.md` | Desarrollo, estructura y uso de cada subproyecto | Cambian estructura, comandos, variables o integración |
| `.env.example` | Variables de entorno con valores de desarrollo | Cambia `config.py` |
| `openspec/config.yaml` | Contexto y reglas que lee OpenSpec al generar artefactos | Cambian stack, estructura, convenciones o reglas de tareas |
| `openspec/specs/` | Specs vigentes por capacidad | Solo mediante `/opsx:sync` desde un change |
| `openspec/changes/` | Changes en curso y archivados | Flujo `/opsx:*` |
| `ai-specs/agents/`, `ai-specs/skills/` | Agentes y skills canónicos, copiados a `.claude/` y `.cursor/` | Cambian patrones de trabajo; re-sincronizar con `sync-agent-symlinks` |

## Cuándo actualizar

- **Endpoint nuevo o modificado**: `README.md` §4 (si es uno de los principales), `docs/documents-api.md` o `docs/admin.md`, `backend/README.md` si cambia el recorrido con `curl`.
- **Modelo de datos**: `README.md` §3, `docs/database.md`, migración Alembic aditiva.
- **Variable de configuración**: `config.py` → `.env.example` → doc del tema → `docs/real-mode.md` si es obligatoria en producción.
- **Agente local**: `docs/agent-contract.md`, `agent/README.md`, `widget/README.md` si cambia lo que el widget espera.
- **Widget**: `widget/README.md` (integración, mensajes, variables), `README.md` §1.2 y §1.3.
- **Panel**: `frontend/README.md` (estructura, CSP), `docs/admin.md`.
- **Seguridad**: `README.md` §2.5 y la doc del componente; el informe de `security-audit` se guarda en `docs/` solo si se pide.
- **Convención nueva** (carpeta, patrón, herramienta): `AGENTS.md`/`CLAUDE.md` y `openspec/config.yaml` antes de usarla por segunda vez.
- **Skill o agente nuevo**: `ai-specs/`, re-sincronizar copias, mencionarlo en `AGENTS.md` §5 y en `prompts.md` si cambia el flujo de trabajo.

## Reglas de OpenSpec

- Mantener `openspec/config.yaml` apuntando a archivos reales; sin referencias a docs renombrados.
- Cada change cita la clave `FIRDOC-N` y la historia de usuario del `README.md` que implementa, e incluye "Fuera de alcance".
- Archivar (`/opsx:archive`) solo después de `/opsx:verify`, `/opsx:sync` y con los tests del área en verde.

## Estilo

- Español para toda la documentación; inglés para identificadores, endpoints, claves de configuración y nombres de archivo.
- Sin nombrar al organismo empleador, la provincia ni al proveedor comercial de referencia.
- Tablas y secciones cortas; este repositorio lo leen personas y agentes con presupuesto de tokens.
- Enlazar al documento autoritativo en lugar de duplicar su contenido.
