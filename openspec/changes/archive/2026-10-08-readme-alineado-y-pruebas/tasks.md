## 1. Capturas del producto (FIRDOC-40)

- [x] 1.1 Script reproducible que levanta el modo demo y guarda en `docs/img/` capturas de: sección «Firmar documento», widget individual (elección de método), widget de lote, listado de Documentos, detalle de custodia e Integradores
- [x] 1.2 Revisar cada captura (sin datos reales ni nombres de organismo o fabricantes) y versionar solo las que aportan

## 2. README alineado (FIRDOC-40)

- [x] 2.1 Secciones 1.2 y 1.3: partir de cargar un PDF (el camino por integrador sigue), describir las pantallas reales y mostrar las capturas
- [x] 2.2 Historia de usuario 1 reescrita para la carga de PDF, con la del integrador como variante
- [x] 2.3 Sección 1.4: instalación real verificada (entorno, migraciones, seed, modo demo, PostgreSQL, widget, agente, SoftHSM) y lo pendiente marcado como tal
- [x] 2.4 Secciones 2.4, 2.6, 6 y 7: sin fabricantes, estado real de los tickets y sección de Pull Requests con los cambios y sus commits
- [x] 2.5 Barrido del README y de `docs/` para que no se nombre al organismo ni a fabricantes y no contradiga el código

## 3. Credenciales y flujos a probar (FIRDOC-41)

- [x] 3.1 Sección 1.5 con las credenciales de demostración (integrador y administrador) y cómo correr todo en limpio
- [x] 3.2 Tabla de flujos con pasos, resultado esperado y la prueba automatizada de cada uno: token de software (SoftHSM), firma propia, lote con fallo parcial, certificado rechazado antes del PIN, agente no detectado, verificación de un documento firmado y webhook
- [x] 3.3 Comprobar de verdad que cada comando y cada prueba citada existen y pasan

## 4. Cierre

- [x] 4.1 Verificar los enlaces relativos y las imágenes del README
- [x] 4.2 Pasar FIRDOC-40 y FIRDOC-41 a Listo en Jira al cerrar el change
