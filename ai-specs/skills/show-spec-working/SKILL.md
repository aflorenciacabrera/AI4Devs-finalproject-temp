---
name: show-spec-working
description: Usar cuando el usuario pide "mostrame X", "demo de X", "probá X", "cómo funciona X" o una demostración en vivo de una spec, feature o ticket de Firmadoc.
author: LIDR.co (adaptado para Firmadoc)
version: 1.1.0
---

# show-spec-working Skill

Demostrar una spec de forma ejecutable, con el modo demostración de Firmadoc.

Si el usuario no da contexto, usar la spec o el change en el que se está trabajando en esta sesión.

Terminar siempre con el informe de cierre en el chat.

## Frases disparadoras (prioridad alta)

Tratar estas expresiones como órdenes de ejecución, no como pedidos de análisis:

- `mostrame X` / `show me X`
- `demo X` / `hacé una demo de X`
- `probá X` / `probalo`
- `cómo funciona X`
- `demostrá que X funciona`

No detenerse en un resumen de la feature.

## Entradas

- Contexto opcional del usuario: clave `FIRDOC-N`, nombre de feature o change, endpoint, pantalla del panel o del widget.
- Si falta, inferirlo del change activo en `openspec/changes/` o de la rama.

## Flujo

### Paso 1: resolver la spec y el alcance

1. Identificar la spec o change (patrón `FIRDOC-[0-9]+` como contexto primario si aparece).
2. Determinar la modalidad:
   - `panel`: comportamiento del panel Angular (`/panel`).
   - `widget`: flujo de firma embebido (`/sign/{id}`), con o sin agente.
   - `api`: solo endpoints.
   - `mixta`.
3. Listar los escenarios concretos a demostrar a partir de los criterios de aceptación de la spec.

### Paso 1.1: no quedarse en un informe

- Nunca terminar con solo el análisis de requisitos.
- Si la ejecución está bloqueada, informar el bloqueo y pedir exactamente lo que falta.

### Paso 2: levantar el entorno

```bash
make demo                 # compila widget y panel si falta el build y arranca en :8000
make demo ARGS=--reset    # empieza de cero (borra data/demo)
make agent                # agente con token de software (PIN 1234) para demostrar el proveedor token
```

`python -m firmadoc.demo` imprime la URL del panel, el token de acceso y la API key de demostración (`firmadoc-demo-key`). Usar `http://localhost:8000` (no `127.0.0.1`): el widget solo se embebe desde el origen configurado. Para el proveedor `firmar`, `FIRMADOC_FIRMAR_MOCK_ENABLED=true` (ver `docs/firmar.md`). Detalle en `docs/demo.md`.

### Paso 3: demostración en el navegador (`panel`, `widget`, `mixta`)

1. Abrir el panel con el navegador integrado, ingresar con el token de acceso impreso por la demo.
2. Recorrer la feature de a una interacción: por ejemplo, **Firmar documento** → cargar PDF → elegir método → (agente) elegir certificado → confirmar → resultado → **Documentos** → detalle de custodia → descarga de la versión.
3. Después de cada acción, verificar que lo visible coincide con la spec (estado, mensajes, versión nueva, auditoría).
4. Dejar el navegador en un estado estable y abierto, salvo que el usuario pida cerrarlo.

### Paso 4: demostración de la API (`api`, `mixta`)

1. Identificar endpoints y payloads de la spec (`README.md` §4, `docs/documents-api.md`, `backend/README.md`).
2. Ejecutar `curl` reales:

```bash
H='X-API-Key: firmadoc-demo-key'
B=$(base64 -w0 documento.pdf)
curl -s -X POST localhost:8000/api/v1/signature-requests -H "$H" -H 'Content-Type: application/json' \
  -d "{\"document_base64\":\"$B\",\"provider\":\"local\",\"signer\":{\"full_name\":\"Ana\",\"identifier\":\"20111111112\",\"email\":\"ana@example.org\"}}"
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/prepare -H "$H"
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/complete -H "$H"
curl -s -o firmado.pdf localhost:8000/api/v1/documents/$DOC/versions/2/download -H "$H"
```

3. Los datos son append-only: no hay "deshacer". Para que la demo sea repetible, usar `make demo ARGS=--reset` al terminar o documentos con nombres que identifiquen la demo.
4. Incluir en el chat el comando y la evidencia clave de la respuesta (concisa, enmascarando tokens y API keys).

## Requisitos del navegador

- Usar las herramientas del navegador integrado; leer la página (`read_page`/`get_page_text`) antes de hacer clic.
- No reintentar a ciegas; si algo bloquea, informar y proponer el siguiente paso.

## Contrato de cierre

Mensaje final con:

1. Spec o change demostrado.
2. Qué se ejecutó: flujos en el navegador y comandos `curl`.
3. Resultado por escenario (pasa/falla con nota breve).
4. Estado de los datos (reseteados / se dejaron / no aplica).
5. Cierre: "Demo completa. Podés seguir revisando en el navegador abierto o pedirme que lo cierre."

```markdown
Demo completada para: <spec/change>

Navegador:
- <paso/resultado>

API:
- <curl + nota de la respuesta>

Datos:
- <reseteados / se dejaron / no aplica>

Siguiente:
- Podés seguir en el navegador abierto o pedirme que lo cierre.
```
