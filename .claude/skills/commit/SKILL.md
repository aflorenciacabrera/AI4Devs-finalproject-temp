---
name: commit
description: Crear commits enfocados y pull requests en GitHub siguiendo el estilo del repositorio de Firmadoc (asunto en español con la clave FIRDOC-N).
author: LIDR.co (adaptado para Firmadoc)
version: 1.1.0
---
# commit Skill

Usar cuando el usuario pide commitear, abrir un PR o preparar el mensaje de commit.

## Rol

Sos experto en control de versiones. Producís commits claros y pull requests que facilitan la revisión y la trazabilidad con el backlog `FIRDOC`.

## Argumentos

**Opcional.** `$ARGUMENTS` puede contener:

- **Nada**: preparar y commitear todos los cambios relevantes del árbol de trabajo y abrir un único PR.
- **Claves de ticket o nombres de feature** (por ejemplo `FIRDOC-58`): preparar y commitear **solo** los cambios que pertenecen a esas features; dejar el resto sin stagear.
- **Modo solo descripción / sin git**: si el usuario dice "sin PR", "solo el commit", "solo el mensaje", "no toques git" o "dry run", **no** ejecutar ningún comando de git ni de `gh`. Solo determinar el alcance, listar qué se stagearía y proponer el mensaje.

## Objetivo

1. Un **commit único y comprensivo** que describa con precisión los cambios relevantes.
2. **Push** de la rama y creación (o actualización) de un **Pull Request** en GitHub.
3. Con argumentos: commitear **solo** lo que corresponde a esas features.

## Proceso y reglas

### 0. Modo solo descripción (verificar primero)

Si el usuario pidió explícitamente no tocar git:

- Hacer solo los pasos 1 a 3: inspeccionar el estado, resolver el alcance y escribir el mensaje completo.
- **No** ejecutar `git add`, `git commit`, `git push` ni `gh pr create`.
- Devolver: lista de archivos (y hunks, si es parcial) y el mensaje propuesto en un bloque copiable. Luego detenerse.

### 1. Inspeccionar el estado

- `git status` y `git diff` (y `git diff --staged` si hace falta).
- Identificar la rama actual. Si es `main`, crear una rama de feature antes de commitear (`feature/<tema>` o `<tema>-vN`, según el historial: `git branch -a`).
- `git log --oneline -10` para imitar el estilo de los mensajes recientes.

### 2. Resolver el alcance

- **Sin argumentos**: todos los cambios relevantes, excluyendo lo que no se commitea: `.env`, `data/`, `backend/trust/*.key`, `tests/pki/out/`, `*.db`, `dist/`, `node_modules/`, `.venv/`, `agent/dist/`, `agent/build/`, `__pycache__/`.
- **Con argumentos**: mapear cada argumento a sus cambios (por ruta, por clave en la rama o por contexto del diff). Stagear solo esos archivos o hunks (`git add -p` si un archivo mezcla cambios). Si nada coincide, informarlo y no commitear.

### 3. Mensaje de commit

- **En español**, como todo el historial del repositorio.
- **Asunto**: una línea descriptiva de lo que cambia, con la clave del ticket entre paréntesis al final cuando aplica. Ejemplos reales:
  - `Diálogo del panel con cabecera separada y en mayúsculas; botón «Firmar» (FIRDOC-58)`
  - `El servicio de firma remota se abre en una ventana emergente que se cierra sola (FIRDOC-59)`
- **Cuerpo** (si hace falta): viñetas o párrafos cortos con qué cambió y por qué (áreas tocadas, comportamiento nuevo, correcciones, tests agregados, docs actualizadas).
- No commitear secretos ni artefactos generados. No nombrar al organismo, la provincia ni al proveedor comercial.
- Si el change de OpenSpec fue archivado en el mismo trabajo, mencionarlo en el cuerpo.

### 4. Commit y push

- Crear el commit con el mensaje del paso 3.
- `git push origin <rama>` (`-u` si la rama no existe en el remoto).

### 5. Pull Request (GitHub)

- El repositorio está en GitHub (`origin`); usar `gh` o el MCP de GitHub.
- **Rama destino: `main`**, salvo que el usuario indique otra.
- Crear o actualizar el PR de la rama actual:
  - **Título**: alineado con el commit, con la clave (`[FIRDOC-58] Diálogo del panel con cabecera separada`).
  - **Descripción**: resumen del conjunto de cambios, enlace al ticket, change de OpenSpec involucrado, cómo se probó (comandos de verificación de `AGENTS.md` §1) y pendientes.
- Si hay checks obligatorios (`.github/workflows/ci.yml`), mencionar que el PR queda listo para revisión cuando pasen.

### 6. Resumen para el usuario

- Qué se commiteó (archivos y alcance).
- Con argumentos: qué features se incluyeron y que el resto quedó sin stagear.
- URL del PR.

## Notas

- No ejecutar comandos destructivos (`git push --force`, `git reset --hard`) sin pedido explícito.
- Si el push es rechazado o hay conflictos, informar y sugerir `git pull --rebase`; no forzar.
- Antes de commitear un cambio sensible (ver `AGENTS.md` §5), confirmar que se corrió `security-audit` o dejarlo anotado en el PR como pendiente.
