## Context

El servidor expone el flujo `create` / `prepare` / `complete` autenticado con la API key del integrador, y el agente local expone `GET /certificates` y `POST /sign` en `127.0.0.1` para orígenes permitidos (contrato en `docs/agent-contract.md`). Falta la interfaz que une ambos, que corre en el navegador de la persona embebida en la pantalla del integrador. El mockup (`design/mockup/Widget*.dc.html`) define las pantallas y el tono (español rioplatense, "Elegí", "Abrilo").

La restricción que más condiciona el diseño: **el navegador no puede tener la API key del integrador**. Hay que dar al widget una credencial propia, mínima y de vida corta.

## Goals / Non-Goals

**Goals:**
- Un widget que complete la firma `token` y `local` de punta a punta, con errores comprensibles y sin tocar nunca el PIN.
- Credencial del widget acotada a una solicitud, sin ampliar lo que puede hacer un token filtrado.
- Embebido seguro: solo los orígenes del integrador pueden enmarcarlo y solo ellos reciben mensajes.
- Verificación real en un navegador, no solo con simulaciones.

**Non-Goals:** elegir método desde el widget, lotes, webhook, panel, B-LT, i18n, tema oscuro (ver "Fuera de alcance" del proposal).

## Decisions

1. **Token del widget: HMAC sin estado, no una fila nueva en la base.** Formato `base64url(payload).base64url(hmac_sha256(secret, payload))` con `payload = {"rid": <id>, "exp": <epoch>}`. No requiere migración ni almacenamiento; la verificación es en tiempo constante (`hmac.compare_digest`). Alternativas descartadas: JWT con biblioteca (dependencia innecesaria para un solo uso), token aleatorio guardado con hash (agrega migración y una consulta; la ventaja de poder revocarlo individualmente no compensa porque la solicitud ya deja de aceptar `prepare`/`complete` al pasar a un estado terminal). Un token filtrado permite, como máximo, completar o consultar **esa** solicitud durante una hora.
2. **El token viaja en el fragmento (`#t=`)**: el navegador no lo envía al servidor, no aparece en registros de acceso ni en el `Referer`. La SPA lo lee, lo guarda en una variable en memoria y limpia el fragmento con `history.replaceState`. Se envía luego como `Authorization: Bearer`. Nunca en `localStorage`/cookies.
3. **Endpoints del widget propios (`/api/v1/widget/requests/{id}/…`) que reutilizan `services/signature_flow`**: una dependencia de FastAPI valida el token, carga la solicitud y arma el `Ctx` con el sistema integrador *de esa solicitud* (en lugar de leerlo de la API key). Así no se duplica la lógica de firma ni sus reglas, solo cambia cómo se autentica. Ninguna ruta de integración acepta el token y viceversa (se prueba).
4. **Mismo origen para la API y el widget**: FastAPI sirve la SPA compilada (`/sign/{id}` y `/widget-assets/*`). El widget llama a su propio origen: **no se necesita CORS en el servidor** y no se amplía su superficie. Alternativa descartada: widget en otro dominio con CORS abierto por origen.
5. **`/sign/{id}` calcula `frame-ancestors` por solicitud** a partir de los `allowed_origins` del integrador (cadena separada por comas ya existente), con `'none'` si está vacía; más `Referrer-Policy: no-referrer` y `Cache-Control: no-store`. No requiere el token (está en el fragmento). Un id inexistente da `404` sin pistas. El HTML es el `index.html` compilado, idéntico para todas las solicitudes; solo cambian las cabeceras.
6. **`postMessage` con destinatarios explícitos**: el widget no puede conocer con certeza el origen de su padre (`document.referrer` y `ancestorOrigins` no son fiables entre navegadores). Como el servidor ya le informa los `allowed_origins` del integrador (que además son los únicos que pueden enmarcarlo por CSP), envía el mensaje una vez **a cada origen permitido**; el navegador entrega solo al que coincida con el origen real del padre y descarta el resto. Nunca `"*"`. El contenido excluye el token y el PDF.
7. **Sin mensajes entrantes**: el widget no registra `window.addEventListener("message")`, para que ninguna página pueda manipularlo.
8. **Web Component como envoltorio del iframe**, no como componente en página: reduce el riesgo (el aislamiento del iframe se mantiene, sin CORS ni estilos filtrados) y mantiene una única implementación. Atributo `signing-url` (el ejemplo del README raíz con `request-id` no puede funcionar sin el token, así que se corrige). Los eventos DOM solo se reemiten si `event.source === iframe.contentWindow` y `event.origin` coincide con el de la `signing-url`.
9. **Stack del cliente: Vite + React + TypeScript estricto**, CSS propio con los tokens del mockup (variables `oklch`, `IBM Plex` empaquetada con `@fontsource`), sin librería de componentes. Dos salidas de compilación: la SPA (`index.html` + `/widget-assets/*`) y `widget.js` (Web Component) como entrada de biblioteca separada.
10. **Estado con una máquina de estados explícita** (`useReducer` con uniones discriminadas), sin XState: `loading → (invalid_link | unsupported | agent_detecting) → choose_certificate | confirm_local → validating → awaiting_pin → completing → success`, con ramas `agent_missing`, `token_missing`, `cert_rejected`, `pin_incorrect`, `pin_locked`, `expired`, `failed`. Las transiciones son una función pura, por lo que se prueban sin DOM.
11. **Clientes tipados y separados**: `serverClient` (contexto, prepare, complete, download) y `agentClient` (certificates, sign) normalizan errores a `{code, status, detail}` y tienen tiempos de espera propios (el `POST /sign` espera a la persona, hasta ~130 s; el resto, segundos). Las respuestas se validan en tiempo de ejecución con guardas mínimas para no confiar ciegamente en el servidor ni en el agente.
12. **Traducción de errores en un solo módulo** (`messages/es.ts`): cada `code` del servidor y del agente tiene un texto, un título y una acción posible; los códigos desconocidos caen en un mensaje genérico sin mostrar el detalle crudo.
13. **Accesibilidad desde el diseño**: una región `aria-live="polite"` global, foco en el `h1` de cada pantalla (`tabIndex=-1`), botones nativos, `role="radio"` real para la lista de certificados, estados que no dependen solo del color. Se verifica con `vitest-axe` en cada pantalla y con la prueba en el navegador.
14. **Pruebas en tres niveles**: unitarias de estado y clientes; de componentes con Testing Library y `vitest-axe`; y la prueba de punta a punta en Chrome con Playwright desde `pytest` (reutiliza la PKI de prueba, el servidor y el agente reales; Chrome del sistema vía `channel="chrome"`, sin descargar navegadores). Se omite si falta Chrome o el widget compilado.
15. **Descarga del PDF sin exponer el token**: `fetch` con `Authorization` → `Blob` → URL de objeto → enlace de descarga; el token no pasa por la barra de direcciones.
16. **Datos mostrados tal como los informa el servidor**: el nivel de firma (`B-B`), la fecha y el certificado se toman de la respuesta; el mockup muestra `B-LT` como ejemplo y no debe copiarse.

## Risks / Trade-offs

- **Token de una hora en memoria del navegador:** un script malicioso dentro del iframe (XSS) podría usarlo. Mitigación: CSP estricta en la página del widget (`script-src 'self'`, sin `unsafe-inline`), sin contenido de terceros, token de alcance mínimo y vida corta.
- **Secreto efímero por defecto:** con varios procesos o reinicios los tokens dejan de valer y las `signing_url` ya entregadas fallan. Se documenta que producción debe fijar `FIRMADOC_SIGNING_SECRET`.
- **`postMessage` a varios orígenes:** si un origen permitido no es el padre, el mensaje se descarta silenciosamente (lo deseado); el costo es no poder avisar de un padre mal configurado. Mitigación: la página de ejemplo y la guía.
- **Permiso de red local de Chrome 142+:** sin la política, la persona verá un aviso al detectar el agente. El estado "agente no detectado" lo explica y apunta a la política.
- **Prueba en navegador real:** más lenta y dependiente de Chrome; por eso es un nivel aparte, omitible, y las reglas de negocio se cubren también en niveles rápidos.
- **Sin Angular real:** el criterio del README se cubre con documentación y una página HTML equivalente; un componente Angular concreto puede romper por detalles de `DomSanitizer` que la guía advierte.
- **`localhost` y contenido mixto:** el widget se sirve por HTTPS en producción y llama a `http://127.0.0.1`; los navegadores lo permiten para loopback. Si algún navegador lo bloqueara habría que dar HTTPS local al agente (fuera de alcance).

## Open Questions

- ¿Los orígenes `allowed_origins` del integrador incluyen siempre el del sistema que embebe (hoy es una cadena libre)? Se asume que sí.
- ¿Cuándo se dará al usuario la elección entre `token` y `local`? Requiere decidir si el proveedor es un conjunto permitido por el integrador (cambio de API).
- ¿El widget debe poder abrirse en una ventana propia además del iframe? Hoy funciona (no hay padre), pero no se prueba ni se documenta.
