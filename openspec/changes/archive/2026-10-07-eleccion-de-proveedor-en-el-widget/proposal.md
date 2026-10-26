## Why

Hoy el proveedor lo fija el sistema integrador al crear la solicitud y el widget solo puede ejecutar ese: si la persona no tiene el agente instalado o ese día no tiene el token, no puede elegir otra forma de firmar. La propuesta prevé que **la persona elija el método** (token, firma electrónica de demostración o servicio remoto) dentro del widget, y que el widget no sea inútil para `firmar` (que ya existe como adaptador).

Backlog: FIRDOC-12 (HU8, elegir proveedor de firma desde el widget).

## What Changes

- **Proveedores permitidos por solicitud** (`provider-selection`): al crear una solicitud el integrador puede enviar `allowed_providers` (subconjunto de los habilitados que incluya a `provider`, que pasa a ser el proveedor inicial). Sin ese campo la solicitud es de un solo método, como hasta ahora.
- **Elección desde el widget** (`provider-selection`): el contexto del widget informa `allowed_providers`; `POST /api/v1/widget/requests/{id}/provider` fija el método elegido mientras la solicitud está `pending` y registra el evento de auditoría `provider_selected`.
- **Pantalla de elección** (`widget-provider-choice`): con más de un método permitido, el widget abre en "¿Cómo querés firmar?" con los métodos habilitados y su descripción (firma digital con token, firma electrónica de demostración, firma con servicio remoto). Desde las pantallas de espera o error (agente no encontrado, elegir certificado, confirmar firma de demostración) se puede **volver a elegir otro método**.
- **Firma remota en el widget** (`widget-provider-choice`): para `firmar` el widget envía el documento al servicio (`prepare`), muestra el enlace "Continuar en el servicio de firma" (se abre en otra pestaña, sin cerrar el widget) y consulta el estado hasta que llega el resultado por callback; luego muestra la firma completada o el error.
- Migración `0005`: `signature_request.allowed_providers`.
- Corrige que el widget trate `firmar` como "no disponible": desde ahora solo es "no disponible" un proveedor que el widget no conoce.

## Capabilities

### New Capabilities

- `provider-selection`: proveedores permitidos por solicitud y elección en el servidor.
- `widget-provider-choice`: pantalla de elección, cambio de método y espera de la firma remota en el widget.

### Modified Capabilities

- `signing-widget`: el proveedor `firmar` deja de estar "no soportado".
- `data-model`: columna `allowed_providers`.

## Impact

- Servidor: modelo y migración `0005`, `create_request`, esquemas, contexto del widget y nueva ruta del widget.
- Widget: tipos y guardas, cliente del servidor, máquina de estados, hook de flujo, tres pantallas nuevas (`ChooseProvider`, `ConfirmRemote`, `RemoteWaiting`), mensajes, enlace "elegir otro método" en pantallas existentes, y pruebas (unitarias, de flujo, de accesibilidad y de punta a punta en Chrome).
- Documentación: guía del widget y de la API actualizadas.

## Fuera de alcance

- Lotes con elección de proveedor (el lote tiene un proveedor fijo).
- Que el integrador restrinja proveedores por integrador de forma global (hoy lo restringe por solicitud).
- Recordar la elección entre sesiones del usuario.
