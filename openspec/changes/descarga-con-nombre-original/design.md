## Context

Ver `proposal.md`. El documento no guarda el nombre del archivo: el panel pone el nombre (sin `.pdf`) en `external_document_id` y `signature_flow.document_name()` lo convertía a `nombre_con_guiones.pdf` reemplazando todo lo que no fuera alfanumérico. Cada endpoint de descarga armaba su propio nombre con sufijo de versión. El widget (`serverClient.download`) y el panel Angular (`admin-api.download`) leen `filename=` de `Content-Disposition` y usan un nombre fijo solo si falta.

## Goals / Non-Goals

**Goals:** un único lugar que decide el nombre; el nombre original en todas las salidas; cabecera correcta con acentos.

**Non-Goals:** tocar el widget (lo está editando otra tarea en paralelo) o el panel; migrar datos.

## Decisions

1. **Módulo `firmadoc/filenames.py`** sin dependencias del modelo (recibe `external_document_id` e `id`), para que lo usen servicios y rutas sin ciclos de importación. `document_name()` en `signature_flow` delega en él: así el widget, el agente y la descarga muestran exactamente el mismo nombre.
2. **Sin sufijo de versión**, como pidió la usuaria: v1 y v2 se descargan con el mismo nombre; el navegador numera si hace falta. En el ZIP, donde sí colisionarían, se numeran con `-2`, `-3`.
3. **Cabecera con `filename` y `filename*`.** Starlette codifica las cabeceras en latin-1: el `filename` lleva los caracteres representables en latin-1 (acentos del español incluidos) y `_` para el resto; `filename*` lleva el nombre completo en UTF-8 percent-encoded. La expresión regular del widget y del panel toma el primer `filename=`, así que ven el nombre con acentos tal cual, y los navegadores que entienden `filename*` ven el nombre exacto.
4. **Limpieza mínima:** NFC, sin `/`, `\`, comillas ni caracteres de control, sin puntos finales, máximo 200 caracteres. La prueba existente «el nombre de archivo descargado se sanea» sigue valiendo.

## Risks / Trade-offs

- [Integradores que dependían de `documento-v{n}.pdf`] → cambio documentado en el README de la API; el contenido y la URL no cambian.
- [Dos descargas (v1 y v2) con el mismo nombre en la misma carpeta] → el navegador agrega «(1)»; es lo que pidió la usuaria.

## Migration Plan

Sin migraciones. Reiniciar el servidor. Rollback: revertir el commit.
