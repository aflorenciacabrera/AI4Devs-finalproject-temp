---
name: update-docs
description: Identificar y actualizar la documentación técnica de Firmadoc afectada por los cambios implementados (docs/, READMEs de subproyectos, README.md, prompts.md).
author: LIDR.co (adaptado para Firmadoc)
version: 1.1.0
---
# update-docs Skill

Usar al cerrar una tarea o un change de OpenSpec, antes de `/opsx:archive`.

## Instrucciones

1. Leer `docs/documentation-standards.md`: tiene el mapa de qué documento se actualiza con cada tipo de cambio.
2. Revisar el diff del cambio (`git diff`, o los artefactos del change activo) y listar qué áreas se tocaron: API, modelo de datos, configuración, agente, widget, panel, proveedores, webhooks, demo.
3. Para cada área, actualizar el documento correspondiente según el mapa. Reglas:
   - En español; identificadores, endpoints y claves de configuración en inglés.
   - Sin nombrar al organismo, la provincia ni al proveedor comercial.
   - Preferir tablas y secciones cortas; enlazar al documento autoritativo en lugar de duplicar.
   - Si cambió `config.py`, actualizar `.env.example` y la doc del tema.
   - Si cambió el flujo visible, regenerar las capturas con `python docs/img/generar.py` y revisar `README.md` §1.3.
4. Verificar que `openspec/config.yaml` y `AGENTS.md` no referencien archivos renombrados o eliminados.
5. Informar qué documentos se actualizaron y cuáles se evaluaron y no necesitaron cambios.
