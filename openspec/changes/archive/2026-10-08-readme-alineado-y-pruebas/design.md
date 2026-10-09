## Context

- `README.md` (621 líneas) sigue la plantilla del máster (secciones 0 a 7). La 1.3 dice «no hay código todavía», la 1.4 es un objetivo y la 7 dice «pendiente». `docker-compose.yml` solo define PostgreSQL; el servidor, el widget y el agente se ejecutan directamente (`python -m firmadoc.demo`, `uvicorn`, `npm run build`, `agent/packaging/build.ps1`).
- Existen `docs/` por tema (admin, demo, real-mode, signature-batches, agent-contract, database, webhooks, timestamping) y 538 pruebas que ya cubren los flujos pedidos, incluidas pruebas en Chrome real.
- No se pueden nombrar el organismo ni fabricantes; el README hoy nombra un token de referencia (2.6).

## Goals / Non-Goals

**Goals:** README verdadero (todo lo que dice se puede ejecutar o comprobar), con capturas del producto, instrucciones reales y la lista de flujos a probar con sus credenciales de demostración.

**Non-Goals:** cambiar código, publicar el mockup, abrir el PR.

## Decisions

1. **Solo se documenta lo que existe.** La 1.4 describe los comandos reales y marca explícitamente lo que no existe (contenedores de la aplicación, despliegue público) como pendiente, en vez de prometerlo.
2. **Capturas generadas, no a mano**: un script con Playwright levanta el modo demo en un puerto libre, recorre las pantallas y guarda PNG en `docs/img/`. Así se pueden regenerar cuando cambie la interfaz y no quedan capturas de otro estado del producto. El script vive en `tests/e2e/`-adyacente pero fuera de la suite (no corre en CI).
3. **Credenciales**: solo las de demostración. La API key del integrador es `firmadoc-demo-key` (fija del seed) y el token de administración lo genera y muestra `python -m firmadoc.demo` (se guarda en `data/demo/demo.json`); el README no incluye un token de administración fijo.
4. **Flujos a probar como tabla** con columnas Flujo, Cómo probarlo, Resultado esperado y Prueba automatizada que lo cubre (nombre del archivo de prueba), para que quien revise pueda tanto recorrerlo a mano como correr la prueba.
5. **Estado en la sección 6 y PRs en la 7**: cada ticket lleva su estado y los commits de la historia; la sección 7 lista los cambios con su commit y aclara que el PR de entrega se abre en FIRDOC-43 (no se inventa un número de PR).
6. **Sin nombres de fabricantes**: se reemplaza el token de referencia por «un token criptográfico USB de referencia», también en el README de `docs/` y del agente si aparece.

## Risks / Trade-offs

- [Capturas con datos de prueba] → se generan con el seed de demostración y nombres ficticios; se revisa cada imagen antes de versionarla.
- [Instrucciones que se desactualizan] → se verifican ejecutando de verdad los comandos de la 1.4 y el modo demo antes de cerrar.
- [README largo] → se agrega la 1.5 y se enlaza a `docs/` en vez de repetir su contenido.

## Open Questions

- Ninguna que cambie el alcance.
