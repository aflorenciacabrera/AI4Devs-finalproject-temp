## Context

Ver `proposal.md`. `RemoteWaiting` renderiza un `<a target="_blank" rel="noopener noreferrer">` con la `authorization_url`; el iframe del widget ya tiene `allow-popups allow-popups-to-escape-sandbox` (FIRDOC-56), así que puede abrir ventanas sin aislamiento. La pantalla se desmonta cuando el estado deja `remote_waiting`.

## Goals / Non-Goals

**Goals:** ventana chica sobre el panel; cierre automático al terminar; sin regresión si el navegador bloquea ventanas emergentes.

**Non-Goals:** comunicar nada entre el widget y la ventana del servicio (el resultado llega por el callback al servidor, como siempre).

## Decisions

1. **`window.open` en el clic del enlace, con el enlace como respaldo.** El `onClick` abre la ventana con `popup=yes,width=520,height=680` centrada y, si obtiene la ventana, hace `preventDefault`; si devuelve `null` (bloqueada), no hace nada y el enlace abre la pestaña. Alternativa descartada: abrirla sola al entrar en la espera (los navegadores la bloquean sin gesto del usuario, y la spec ya pedía no abrirla automáticamente).
2. **Con `opener`, para poder cerrarla.** `window.open` con `noopener` devuelve `null`, así que la ventana conserva `opener`. Riesgo: el servicio podría navegar la ventana que lo abrió (el iframe del widget). Mitigación: el iframe está aislado con `sandbox` sin `allow-top-navigation`, con lo que no puede tocar la página anfitriona; y el servicio es una parte confiable del flujo (en la demo, el simulado del propio servidor). El enlace de respaldo lleva `rel="noreferrer"` (que implica `noopener` para la pestaña).
3. **Cierre al desmontar.** Un `useRef` guarda la ventana y el efecto de limpieza la cierra si no está cerrada: cubre firmado, rechazo, vencimiento y «Cancelar». `close()` sobre una ventana de otro origen abierta por script está permitido.
4. **Texto del simulado.** La página de resultado dice que la ventana se cierra sola (y cómo cerrarla si no), en lugar de «volvé a la pestaña».

## Risks / Trade-offs

- [Bloqueo de ventanas emergentes] → se abre una pestaña, como hasta ahora.
- [Persona cierra la ventana antes de terminar] → el widget sigue esperando; el enlace permite abrirla de nuevo.

## Migration Plan

Sin migraciones. Rollback: revertir el commit.
