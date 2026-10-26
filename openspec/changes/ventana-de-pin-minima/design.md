## Context

Ver `proposal.md`. `PinDialog` (`agent/src/firmadoc_agent/ui_tk.py`) arma la ventana con tkinter a partir de `SignPrompt(document_names, certificate_subject, last_try_warning)`; `subject_parts()` extrae CN y CUIL del sujeto. El servicio (`service.py`) arma el `SignPrompt` y registra los nombres de documentos en el log al firmar.

## Goals / Non-Goals

**Goals:** una ventana con tres elementos: nombre, PIN, botones. Mismo comportamiento de seguridad (un intento, sin reintentos, PIN borrado del widget, tiempo límite).

**Non-Goals:** tocar `SignPrompt`, el servicio, el servidor HTTP del agente o el widget.

## Decisions

1. **Quitar widgets, no datos.** `PinDialog` deja de crear las etiquetas de CUIL y sujeto y el `Listbox` de documentos. `SignPrompt` conserva sus campos: el servicio los sigue usando para el log, y así `try_dialog.py` y las pruebas del servicio no cambian. Alternativa descartada: recortar `SignPrompt`, que obligaría a tocar el servicio sin beneficio.
2. **`subject_parts()` se mantiene** (devuelve CN y CUIL): la ventana usa solo el CN; el CUIL deja de mostrarse. No se borra la función para no romper su prueba unitaria y porque el diagnóstico la puede reutilizar.
3. **Etiqueta de contexto breve** encima del nombre («Firmar con el certificado de») para que la ventana diga qué es sin agregar datos.
4. **Pruebas:** `test_muestra_nombres_y_certificado` pasa a comprobar que los nombres de documentos, la cantidad, el CUIL y el sujeto **no** aparecen; `test_titular_y_cuil_destacados` pasa a «titular destacado sin CUIL». El resto (enmascarado, cancelar, tiempo, hilo) no cambia.

## Risks / Trade-offs

- [El usuario ya no ve qué documento firma en la ventana del agente] → lo ve en el widget, que lista los documentos antes de llamar al agente; los nombres siguen en el registro del agente. Es la decisión de producto de la usuaria y queda escrita en la spec.

## Migration Plan

Reiniciar el agente para tomar el cambio. Rollback: revertir el commit.
