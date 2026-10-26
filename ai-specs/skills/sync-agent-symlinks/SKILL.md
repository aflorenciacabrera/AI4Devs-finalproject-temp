---
name: sync-agent-symlinks
description: Sincronizar las copias de skills y agentes en .claude/ y .cursor/ después de cambios en ai-specs/ (altas, bajas, renombres). Usar siempre que se agregue o edite algo en ai-specs/skills o ai-specs/agents.
author: LIDR.co (adaptado para Firmadoc)
version: 1.1.0
---

# sync-agent-symlinks Skill

Mantener las carpetas de cada herramienta alineadas con `ai-specs/` como fuente canónica.

En Firmadoc (Windows) **no se usan symlinks**: son copias de archivos, porque los symlinks requieren permisos elevados. El nombre del skill se conserva por compatibilidad con los demás proyectos.

## Alcance y reglas de seguridad

- Fuente canónica: `ai-specs/skills/<skill>/` y `ai-specs/agents/<agente>.md`.
- Destinos:
  - `.claude/skills/<skill>/` y `.claude/agents/<agente>.md`
  - `.cursor/skills/<skill>/` y `.cursor/agents/<agente>.md`
- **No tocar** las entradas generadas por la CLI de OpenSpec: `.claude/skills/openspec-*`, `.cursor/skills/openspec-*`, `.claude/commands/opsx/`, `.cursor/commands/opsx-*`. Son externas; se regeneran con `openspec update`.
- No borrar carpetas de los destinos que no existan en `ai-specs/` sin preguntar: informarlas como huérfanas.
- Nunca editar una copia a mano: editar en `ai-specs/` y re-sincronizar.

## Flujo

### Paso 1: inventario

1. Skills canónicos: carpetas de `ai-specs/skills/*` con `SKILL.md`.
2. Agentes canónicos: `ai-specs/agents/*.md`.
3. Entradas en cada destino, clasificadas:
   - `sincronizada`: existe y su contenido coincide con la canónica.
   - `desactualizada`: existe pero difiere.
   - `faltante`: canónica sin copia en el destino.
   - `huérfana`: copia sin canónica (y que no sea `openspec-*`).
   - `externa`: `openspec-*` u otra entrada que no gestiona este skill.

### Paso 2: plan

Por destino: `a_agregar`, `a_actualizar`, `a_eliminar` (solo huérfanas confirmadas por el usuario), `a_omitir` (externas).

### Paso 3: aplicar

```bash
# Git Bash
for s in ai-specs/skills/*/; do n=$(basename "$s"); for t in .claude .cursor; do rm -rf "$t/skills/$n"; cp -r "$s" "$t/skills/$n"; done; done
for a in ai-specs/agents/*.md; do for t in .claude .cursor; do mkdir -p "$t/agents"; cp "$a" "$t/agents/"; done; done
```

```powershell
# PowerShell
Get-ChildItem ai-specs/skills -Directory | ForEach-Object { foreach ($t in '.claude','.cursor') { Remove-Item "$t/skills/$($_.Name)" -Recurse -Force -ErrorAction SilentlyContinue; Copy-Item $_.FullName "$t/skills/$($_.Name)" -Recurse } }
Get-ChildItem ai-specs/agents -Filter *.md | ForEach-Object { foreach ($t in '.claude','.cursor') { New-Item -ItemType Directory -Force "$t/agents" | Out-Null; Copy-Item $_.FullName "$t/agents/" -Force } }
```

Si `AGENTS.md` cambió, copiarlo también a `CLAUDE.md` (son idénticos).

### Paso 4: verificar

```bash
for s in ai-specs/skills/*/; do n=$(basename "$s"); diff -rq "$s" ".claude/skills/$n" && diff -rq "$s" ".cursor/skills/$n"; done
for a in ai-specs/agents/*.md; do diff -q "$a" ".claude/agents/$(basename "$a")" && diff -q "$a" ".cursor/agents/$(basename "$a")"; done
diff -q AGENTS.md CLAUDE.md
```

Sin salida = todo sincronizado.

### Paso 5: informe

- Cantidad de skills y agentes canónicos.
- Por destino: agregados, actualizados, eliminados, huérfanos, externos omitidos.
- Bloqueos pendientes.

## Señales de alerta

Nunca:
- tratar `.claude/` o `.cursor/` como fuente de verdad;
- borrar `openspec-*` ni los comandos `opsx`;
- dejar copias desactualizadas después de editar `ai-specs/`.

Siempre:
- analizar antes de cambiar;
- aplicar el mínimo de cambios;
- cerrar con el informe y la verificación con `diff`.
