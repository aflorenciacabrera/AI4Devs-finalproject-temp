## ADDED Requirements

### Requirement: Firma remota con el servicio simulado
El modo demostración SHALL habilitar el proveedor `firmar` contra el servicio de firma remota simulado del mismo servidor (`FIRMADOC_FIRMAR_BASE_URL` = `http://localhost:{puerto}/mock/firmar`, `FIRMADOC_FIRMAR_MOCK_ENABLED=true`), de modo que un PDF cargado desde el panel ofrezca «Firma remota» entre sus métodos y el flujo se complete desde el navegador: el widget abre la página de autorización del simulado, la persona ingresa OTP `123456` y PIN `1234`, y la solicitud queda firmada con una versión nueva cuya cadena llega a la AC del simulado. El comando SHALL generar una única vez un secreto de cliente y un secreto de callback (de al menos 32 caracteres), guardarlos en `data/demo/demo.json` junto a los existentes y reutilizarlos; en un `demo.json` anterior SHALL agregarlos sin regenerar el token de administración ni el secreto del widget. La guía SHALL explicar el recorrido y los códigos. Los lotes del panel SHALL seguir sin ofrecer la firma remota.

#### Scenario: Tarjeta disponible
- **WHEN** se carga un PDF desde el panel de la demo
- **THEN** el contexto del widget incluye `firmar` entre `allowed_providers` y la tarjeta «Firma remota» se muestra habilitada

#### Scenario: Firma remota de punta a punta
- **WHEN** se elige «Firma remota», se abre la `authorization_url` y se envía el formulario con OTP `123456` y PIN `1234`
- **THEN** el simulado llama al callback, la solicitud pasa a `signed` y la versión 2 del documento lleva una firma verificable contra la AC del simulado

#### Scenario: Secretos conservados y completados
- **WHEN** se prepara el entorno dos veces, o sobre un `demo.json` que solo tiene el token de administración y el secreto del widget
- **THEN** los secretos de cliente y de callback son los mismos entre arranques, miden al menos 32 caracteres, y el token de administración y el secreto del widget anteriores se conservan

#### Scenario: Lote desde el panel
- **WHEN** se cargan varios PDF desde el panel de la demo
- **THEN** el lote ofrece solo `token` y `local`

## MODIFIED Requirements

### Requirement: Guía al arrancar
Al arrancar el comando SHALL mostrar la URL del panel, el token de administración, la API key de demostración, el método a usar sin token («Firma propia») y cómo probar la firma remota con el servicio simulado (OTP `123456` y PIN `1234`), y SHALL avisar, sin impedir el arranque, si el widget no está compilado indicando cómo compilarlo.

#### Scenario: Widget sin compilar
- **WHEN** no existe `widget/dist/index.html`
- **THEN** el servidor arranca y el aviso indica `npm run build` en `widget/`

#### Scenario: Datos de acceso
- **WHEN** el entorno está listo
- **THEN** se imprime la URL de `/admin`, el token de administración y el uso de «Firma propia»

#### Scenario: Firma remota en la guía
- **WHEN** el entorno está listo
- **THEN** la guía indica elegir «Firma remota», continuar en el servicio simulado e ingresar OTP `123456` y PIN `1234`
