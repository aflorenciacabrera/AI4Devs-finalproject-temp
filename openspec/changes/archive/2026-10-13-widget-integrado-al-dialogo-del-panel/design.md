## Context

Ver `proposal.md`. El widget dibuja cada pantalla con `Screen` (cabecera `.brandbar`, `.card` con borde y fondo, `.actions` al pie) sobre un `body` con fondo gris; solo tiene tokens claros. El panel Angular tiene tema claro/oscuro (`data-theme` en `<html>`, `Theme`) y abre el widget en un `DynamicDialog` cuyo contenido es el iframe (`widget-dialog.ts`). El token de firma viaja en el fragmento y `takeToken` lo borra de la URL antes de dibujar; la ruta `/sign/{id}` ignora la query.

## Goals / Non-Goals

**Goals:** que el widget parezca parte del diálogo en claro y en oscuro; menos texto en cada pantalla sin perder lo necesario para operar; el panel como antes de FIRDOC-57.

**Non-Goals:** mensajes entrantes para cambiar el tema en vivo (el diálogo es modal y el tema se fija al abrirlo); personalización de colores por integrador.

## Decisions

1. **Marco fuera, estructura igual.** `Screen` deja de renderizar `.brandbar`; `.card` pierde borde, fondo, radio y las franjas `card--error/success`; `body` y `.shell` quedan transparentes y sin padding. Se conservan las clases (`card`, `card--error`, `body`, `actions`) para no tocar las pruebas que las usan como selectores. El pie `.actions` queda con una línea superior y sin fondo.
2. **Tema por parámetro de consulta.** `main.tsx` lee `theme` de `location.search`; `light`/`dark` fijan `data-theme` en `<html>`; otro valor o ausencia → esquema del sistema. `tokens.css` define los colores oscuros bajo `:root[data-theme="dark"]` y bajo `@media (prefers-color-scheme: dark)` para `:root:not([data-theme="light"])`. El panel inserta `?theme=<actual>` antes del `#` de la `signing_url` al abrir el diálogo. Alternativa descartada: heredar colores del anfitrión (imposible entre orígenes).
3. **Qué texto se va.** Regla: si el título, el subtítulo o un dato visible ya lo dicen, la aclaración sobra. Se mantienen los textos que orientan una acción (PIN en Firmadoc Agent, lista de comprobaciones cuando no hay agente, motivo del rechazo, enlace al servicio remoto) y los que la spec exige (la tarjeta de demostración aclara que no tiene presunción legal, en una línea).
4. **Panel: restaurar, no reescribir.** `sign.ts`, `sign.html` y `sign.spec.ts` vuelven al estado del commit anterior a FIRDOC-57 (`git checkout c92655a`), y `widget-dialog.ts` solo agrega el tema a la URL. `widget-window.ts` se elimina del panel; el soporte de `window.opener` en el widget y `mode=popup` en la página de ejemplo quedan para integradores.

## Risks / Trade-offs

- [El widget flat sobre una página anfitriona sin fondo definido] → la página de ejemplo y el panel estático ya enmarcan el iframe; la guía lo aclara.
- [Tema del panel cambiado con el diálogo abierto] → el diálogo es modal (la barra con el botón de tema queda detrás de la máscara); al reabrir se toma el tema actual.
- [Pruebas que buscaban textos eliminados] → se actualizan a los textos que quedan.

## Migration Plan

Sin migraciones. Rollback: revertir el commit.
