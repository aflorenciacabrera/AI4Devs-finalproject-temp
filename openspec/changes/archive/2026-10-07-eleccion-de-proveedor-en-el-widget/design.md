## Context

`SignatureRequest.provider` es el proveedor activo y los endpoints del widget (`prepare`/`complete`) ya funcionan para cualquiera de ellos. Falta decidir **quién y cuándo** cambia ese valor, y cómo el widget representa a `firmar` (asíncrono, con una pestaña externa).

## Goals / Non-Goals

**Goals:** que el integrador pueda ofrecer varios métodos y la persona elegir; que el cambio sea seguro (no se pisa una firma en curso, no se habilita un método que el integrador no permitió); que `firmar` funcione de punta a punta en el widget.

**Non-Goals:** lotes, recordar la elección, restricción global por integrador (ver proposal).

## Decisions

1. **El integrador decide qué métodos ofrece; la persona, cuál usa.** `allowed_providers` viaja en la creación de la solicitud (el integrador conoce a su usuario y su política). El widget nunca puede elegir un método que el integrador no permitió ni uno no habilitado en el servidor. Alternativa descartada: ofrecer siempre todos los habilitados (un integrador que solo acepta firma digital podría recibir firmas de demostración).
2. **`provider` sigue siendo el proveedor activo**, ahora también el inicial; cambiarlo es una operación explícita (`POST …/provider`) y auditada (`provider_selected` con origen y destino). Se evita agregar un valor "sin elegir" al enum (obligaría a cambiar el CHECK de la base y a todo el código que asume un proveedor concreto).
3. **Solo se puede cambiar en `pending`.** Una vez `signing` hay un desafío preparado o una operación remota abierta: cambiar de método dejaría estado huérfano. Para `token` y `local` se vuelve a `pending` solo si no se preparó nada; el widget no ofrece "elegir otro método" en pantallas posteriores a `prepare` (esperando PIN, firmando). Con `firmar` en espera tampoco: la operación en el servicio queda abierta.
4. **Almacenamiento**: `allowed_providers` como texto separado por comas (3 valores posibles, orden estable), nulo = solo el proveedor de la solicitud. Más simple que una tabla y consistente con `allowed_origins`.
5. **Validación en la creación**: cada valor debe ser un proveedor conocido y **habilitado** (`firmar` solo con servicio configurado), sin repetidos, e incluir a `provider`; si no, `422`. Un método que luego se deshabilita queda fuera del contexto del widget (se filtra con los habilitados al responder).
6. **Firma remota en el widget**: `prepare` devuelve `remote.authorization_url`; el widget lo muestra como enlace con `target="_blank"` y `rel="noopener noreferrer"` (nunca abre ventanas solo, para no chocar con bloqueadores) y consulta `GET` del contexto cada pocos segundos hasta que el callback deja la solicitud `signed` o `failed`. El token del widget sigue siendo el de la solicitud; la URL del servicio la define el servidor (no es entrada del usuario). Si se recarga la página con la solicitud en `signing` y `firmar`, se muestra la espera sin enlace (el servidor no guarda la URL) y se avisa que debe retomarse desde la pestaña del servicio.
7. **Máquina de estados pura, con tres estados nuevos** (`choose_provider`, `confirm_remote`, `remote_waiting`) y dos eventos (`provider_selected`, `remote_started`); el sondeo y las llamadas viven en el hook, como el resto de los efectos. El agente (token) se crea al elegir ese método, no al abrir el widget, de modo que quien elige otro método no dispara la detección del agente ni su petición de red local.
8. **Mensaje al integrador**: el evento `ready` y los de resultado no cambian; `signed` ya trae el documento. No se agrega un mensaje nuevo por la elección (el integrador la ve en la auditoría y en `provider` de la solicitud).

## Risks / Trade-offs

- Con `firmar` el widget no puede saber que la persona cerró la pestaña del servicio sin firmar: se queda esperando hasta el rechazo/vencimiento que informe el servicio. Se ofrece cancelar (la solicitud queda `signing`; la resuelve el callback o el integrador).
- El sondeo cada 3 s por solicitud es tráfico adicional pequeño; se corta al salir de la pantalla y se limita a una consulta por vez.
