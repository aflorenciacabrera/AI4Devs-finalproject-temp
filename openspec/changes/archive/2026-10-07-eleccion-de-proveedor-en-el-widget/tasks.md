## 1. Servidor

- [x] 1.1 Columna `allowed_providers` y migración `0005` reversible con su prueba
- [x] 1.2 `create_request`: validar y guardar `allowed_providers` (conocidos, habilitados, sin repetidos, con el proveedor inicial); campo en el esquema de creación
- [x] 1.3 Contexto del widget con `allowed_providers` (filtrado por habilitados)
- [x] 1.4 `POST /api/v1/widget/requests/{id}/provider` con auditoría `provider_selected`
- [x] 1.5 Pruebas del servidor: creación (válidas e inválidas), contexto, elección (válida, no permitida, estado distinto de `pending`, mismo proveedor, sin token)

## 2. Widget: contratos y estado

- [x] 2.1 Tipos, guardas y cliente (`selectProvider`, `remote` en `prepare`)
- [x] 2.2 Máquina de estados: `choose_provider`, `confirm_remote`, `remote_waiting`, eventos y "elegir otro método"
- [x] 2.3 Hook de flujo: elegir método (crea el agente solo para token), cambiar, confirmar remoto, sondeo con corte al salir
- [x] 2.4 Mensajes en español

## 3. Widget: pantallas

- [x] 3.1 `ChooseProvider`, `ConfirmRemote` y `RemoteWaiting`
- [x] 3.2 "Elegir otro método" en agente no encontrado, problema del agente, elegir certificado, certificado rechazado y confirmar firma de demostración
- [x] 3.3 Pruebas de la máquina, del flujo (incluida la espera remota con reloj controlado), de los clientes y de accesibilidad de las pantallas nuevas

## 4. Punta a punta y documentación

- [x] 4.1 Prueba en Chrome: solicitud con `[token, local]`, elegir local y firmar; y solicitud `firmar` con el simulado desde el widget
- [x] 4.2 Actualizar `widget/README.md`, la guía Angular y `docs` de la API (campo `allowed_providers`)
- [x] 4.3 Ejecutar `pytest`, `ruff`, `vitest`, `tsc` y `eslint` sin errores y recompilar el widget
