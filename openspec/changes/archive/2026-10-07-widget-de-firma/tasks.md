## 1. Servidor: token del widget

- [x] 1.1 Agregar a `Settings` y `.env.example` `signing_secret`, `signing_token_ttl_seconds` (3600), `agent_url` (`http://127.0.0.1:47123`) y `widget_dist` (`widget/dist`); validar que el secreto tenga al menos 32 caracteres y generar uno efímero con advertencia si falta
- [x] 1.2 Implementar `signing_token.py`: emitir y verificar tokens HMAC-SHA256 (`rid`, `exp`) con comparación en tiempo constante
- [x] 1.3 Hacer que `signing_url` devuelva `{public_base_url}/sign/{id}#t={token}` (creación y consulta de la solicitud) y ajustar el test existente
- [x] 1.4 Tests del token: válido, de otra solicitud, vencido, alterado, otro secreto, secreto corto, secreto efímero con advertencia

## 2. Servidor: endpoints del widget

- [x] 2.1 Dependencia de autenticación del widget (`Authorization: Bearer`) que valide el token, cargue la solicitud y construya el `Ctx` con el integrador de esa solicitud
- [x] 2.2 `GET /api/v1/widget/requests/{id}`: contexto (estado, proveedor, nombre del documento, nombre del firmante, `allowed_origins`, `agent_url`, vencimiento del token y bloque `document` si ya está firmada)
- [x] 2.3 `POST .../prepare` y `POST .../complete` reutilizando `signature_flow`, con `X-Session-Ref`
- [x] 2.4 `GET .../download` del PDF de la versión generada por la solicitud (`409` si no está firmada)
- [x] 2.5 Tests: flujo `local` y `token` completos con el token del widget, mismos códigos de error que la API de integración, otra sesión, descarga antes y después de firmar, y que el contexto no exponga datos del integrador
- [x] 2.6 Tests de aislamiento: el token no abre `/api/v1/signature-requests` ni `/api/v1/documents`, y la API key no abre los endpoints del widget

## 3. Servidor: entrega del widget

- [x] 3.1 `GET /sign/{id}`: servir el `index.html` compilado con `frame-ancestors` de los orígenes permitidos del integrador (`'none'` si no hay), `Referrer-Policy: no-referrer`, `Cache-Control: no-store` y una CSP estricta de la página; `404` para ids inexistentes y `503` si el widget no está compilado
- [x] 3.2 Montar `/widget-assets/*` y `/widget.js` desde `widget_dist` solo si existe; el servidor arranca igual sin él
- [x] 3.3 Tests: cabeceras con uno, varios y ningún origen, id inexistente, widget sin compilar, tipos de contenido de los estáticos y que la API siga funcionando

## 4. Widget: proyecto y base

- [x] 4.1 Crear el proyecto en `widget/` (Vite, React, TypeScript estricto, Vitest, Testing Library, `vitest-axe`, ESLint), scripts `dev`, `build`, `test`, `lint`, `typecheck`, y proxy de desarrollo hacia el servidor
- [x] 4.2 Tokens de diseño del mockup (`oklch`, tipografías IBM Plex empaquetadas), estilos base y componentes mínimos (tarjeta, botón, insignia de estado, lista de datos)
- [x] 4.3 Módulo de arranque: leer el token del fragmento, limpiar la URL, guardarlo solo en memoria
- [x] 4.4 Módulo `messages/es.ts` con el texto de cada código de error del servidor y del agente, y el mensaje genérico para códigos desconocidos
- [x] 4.5 Tests del arranque y de los mensajes (cobertura de todos los códigos de `docs/agent-contract.md`)

## 5. Widget: clientes del servidor y del agente

- [x] 5.1 `serverClient`: contexto, `prepare`, `complete` y descarga, con errores normalizados `{code, status, detail}` y guardas de forma sobre las respuestas
- [x] 5.2 `agentClient`: `certificates` y `sign` con tiempos de espera propios (el de `/sign` cubre la espera de la persona) y distinción entre agente ausente y errores del agente
- [x] 5.3 Tests de ambos clientes con `fetch` simulado: respuestas correctas, cada código de error, red caída, tiempo agotado y respuestas mal formadas

## 6. Widget: estado y pantallas

- [x] 6.1 Máquina de estados pura (`reducer`) con todas las transiciones del diseño y tests unitarios por transición
- [x] 6.2 Pantallas de carga y de enlace inválido o vencido, y de método no disponible (`firmar`)
- [x] 6.3 Detección del agente: agente no detectado (con las tres comprobaciones y "Reintentar detección"), token sin conectar, sitio no autorizado y biblioteca del token
- [x] 6.4 Elección del certificado (lista accesible con vencidos deshabilitados) y "Validar y continuar"
- [x] 6.5 Certificado rechazado antes del PIN, con el motivo traducido y "Elegir otro certificado"
- [x] 6.6 Espera de la confirmación en el agente y manejo de `user_cancelled`, `pin_incorrect` (reintento manual), `pin_locked` y `busy`
- [x] 6.7 Desafío vencido: volver a empezar con el mismo certificado
- [x] 6.8 Firma con proveedor `local` (un solo paso de confirmación)
- [x] 6.9 Firma completada con los datos del servidor, descarga del PDF por `Blob` y "Cerrar"; "Cancelar" en las pantallas previas
- [x] 6.10 Accesibilidad: región `aria-live`, foco en el título de cada pantalla, navegación por teclado; test `vitest-axe` por pantalla
- [x] 6.11 Tests de componentes de cada pantalla y del flujo completo `token` y `local` con clientes simulados, y de que ni el token ni las firmas lleguen a `localStorage`, `sessionStorage`, cookies ni consola

## 7. Embebido

- [x] 7.1 Módulo de mensajes hacia el anfitrión (`firmadoc:ready|signed|failed|cancelled|closed`) con `targetOrigin` explícito por cada origen permitido, sin token ni PDF y sin escuchar mensajes entrantes
- [x] 7.2 Web Component `<firmadoc-widget signing-url>` (iframe interno, eventos DOM solo desde su propio iframe y origen, recarga al cambiar el atributo) y su compilación a `widget.js`
- [x] 7.3 Página anfitriona de ejemplo (iframe y Web Component) que muestra los mensajes recibidos
- [x] 7.4 Tests de mensajes y del Web Component en jsdom: destinatarios, contenido, ignorar mensajes entrantes, eventos desde ventana y origen ajenos
- [x] 7.5 `widget/README.md`: uso por iframe y Web Component, contrato de mensajes, guía Angular (`DomSanitizer`, validación de origen y ventana, `CUSTOM_ELEMENTS_SCHEMA`), obtención de la `signing_url` desde el backend, y configuración de variables del servidor
- [x] 7.6 Corregir el ejemplo del Web Component del README raíz (`signing-url` en lugar de `request-id`)

## 8. Prueba de punta a punta en Chrome

- [x] 8.1 Infraestructura en `tests/e2e/`: servidor Firmadoc real (con el widget compilado), agente real con `SoftwareBackend` y UI de prueba, página anfitriona en otro origen, y Playwright con Chrome del sistema; omitir con motivo si falta Chrome o el widget compilado
- [x] 8.2 Flujo `token` completo dentro del iframe: la página anfitriona recibe `firmadoc:signed` y el PDF descargado tiene una firma válida
- [x] 8.3 Casos: certificado revocado rechazado antes del PIN, agente no disponible y reintento de detección, cancelación en el agente, PIN incorrecto con reintento manual
- [x] 8.4 Firma `local` y Web Component embebido
- [x] 8.5 Un origen no permitido no puede enmarcar el widget ni recibe mensajes
- [x] 8.6 Comprobar en el navegador que el token no queda en la URL, el historial, el almacenamiento ni la consola

## 9. Compilación, CI y cierre

- [x] 9.1 Compilar el widget y verificar que el servidor lo sirve desde `widget/dist`; `widget/dist` fuera de git
- [x] 9.2 Ampliar `.github/workflows/ci.yml`: compilación, tipos, lint y pruebas del widget, y la prueba de punta a punta con Chrome
- [x] 9.3 Ejecutar `pytest`, `ruff check`, y en `widget/` `typecheck`, `lint` y `test` sin errores
