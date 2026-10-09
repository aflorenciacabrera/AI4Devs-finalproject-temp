## Why

El README se escribió antes del código y quedó atrás de lo implementado y de las decisiones del 07/10/2026: describe «no hay código todavía», parte de un documento que ya existe en el sistema integrador en vez de cargar un PDF, plantea una instalación con contenedores que no existen (solo hay PostgreSQL en `docker-compose.yml`), y no tiene capturas. Además la entrega pide credenciales de prueba y una lista explícita de flujos a probar. Implementa **FIRDOC-40** (README alineado con el código, los `docs/` y el mockup) y **FIRDOC-41** (credenciales de prueba y flujos a probar), dentro de la épica de documentación y entrega (FIRDOC-5).

## What Changes

- **1.2 y 1.3**: reflejan que en general **se parte de cargar un PDF** (el camino por sistema integrador sigue existiendo); la 1.3 describe las pantallas reales y trae **capturas del producto** (sección «Firmar documento», widget individual y en lote, detalle de custodia, listado, integradores).
- **Historia de usuario 1**: reescrita para la carga de PDF desde el navegador; la historia del sistema integrador queda como variante.
- **1.4 Instalación**: documenta lo real (requisitos, entorno virtual, migraciones, seed, modo demo `python -m firmadoc.demo`, PostgreSQL con `docker compose`, widget, agente empaquetado y SoftHSM), sin prometer contenedores que no existen.
- **Nueva 1.5 Credenciales de prueba y flujos a probar**: credenciales solo de demostración y una tabla de flujos con pasos, resultado esperado y la prueba automatizada que los cubre (firma con token de software, firma propia, lote con fallo parcial, certificado rechazado antes del PIN, agente no detectado, verificación, webhook), y cómo correr todo en limpio.
- **Secciones 2.6, 6 y 7**: se quita el nombre del fabricante del token de referencia, se agrega el estado real de cada ticket y la sección de Pull Requests deja de decir «pendiente» (lista los cambios con su commit; el PR de entrega es FIRDOC-43).
- **Capturas** reproducibles en `docs/img/`, generadas con un script que levanta el modo demo en un Chrome real.

## Capabilities

### New Capabilities
<!-- Ninguna: cambio solo de documentación. -->

### Modified Capabilities
<!-- Ninguna: no cambia ningún requisito del sistema (el change declara skip_specs). -->

## Impact

- Archivos: `README.md`, `docs/img/*.png` y el script que las genera (`docs/img/generar.py` o equivalente bajo `tests/`), sin cambios en el código del producto.
- Dependencias: ninguna nueva (Playwright ya se usa en las pruebas de punta a punta).

## Fuera de alcance

- Ficha del proyecto (0.4 URL pública, 0.5 repositorio): dependen del despliegue y de la entrega (FIRDOC-42, 43).
- Actualizar el canvas del mockup y publicarlo (FIRDOC-39): requiere la herramienta de diseño.
- Abrir el pull request y enviar el formulario (FIRDOC-43).
- Reescribir las secciones 3 y 4 (modelo de datos y API) más allá de lo necesario para no contradecir el código.
- Nombrar al organismo o a fabricantes: el README debe seguir sin hacerlo.
