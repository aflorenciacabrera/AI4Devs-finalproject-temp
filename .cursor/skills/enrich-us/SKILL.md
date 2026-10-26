---
name: enrich-us
description: Analizar y enriquecer historias de usuario o tickets del backlog FIRDOC en Jira hasta dejarlos listos para implementar con detalle técnico completo.
author: LIDR.co (adaptado para Firmadoc)
version: 1.1.0
---
# enrich-us Skill

Usar cuando el usuario pide refinar, enriquecer o completar un ticket de Jira.

## Instrucciones

Analizá y completá el ticket de Jira: $ARGUMENTS.

1. Obtener el ticket con el MCP de Atlassian (proyecto `FIRDOC`, sitio `aflorenciacabrera.atlassian.net`), ya sea por clave (`FIRDOC-N`), por palabras clave o por estado ("el que está en progreso").
2. Actuar como product owner con conocimiento técnico del proyecto.
3. Entender el problema descripto y ubicarlo en el contexto de Firmadoc: historia de usuario de `README.md` §5, ticket de §6, specs vigentes en `openspec/specs/` y documentación en `docs/`.
4. Decidir si la historia está completamente detallada según buenas prácticas de producto: descripción completa de la funcionalidad, campos y entidades afectadas (`README.md` §3, `docs/database.md`), endpoints necesarios con su contrato (`README.md` §4, `docs/documents-api.md`), archivos a modificar según la arquitectura (`AGENTS.md` §1, agentes `backend-developer` / `frontend-developer`), criterios de aceptación verificables, tests requeridos (área y casos de rechazo), documentación a actualizar y requisitos no funcionales (seguridad según `README.md` §2.5, rendimiento, accesibilidad del widget).
5. Si falta detalle para que quien implemente sea autónomo, redactar una versión mejorada: más clara, específica y concisa, en español, respetando la confidencialidad (sin nombrar organismo, provincia ni proveedor comercial). Devolverla en markdown.
6. Actualizar el ticket en Jira agregando el contenido nuevo después del original, con encabezados h2 `[original]` y `[mejorada]`, con formato legible (listas, bloques de código para endpoints y payloads).
7. Si el tablero tiene columnas de refinamiento (por ejemplo "To refine" → "Pending refinement validation"), mover el ticket; si no, dejar el estado como está e informarlo.
8. Sugerir, si corresponde, el nombre kebab-case del change de OpenSpec para `/opsx:propose`.
