## Context

`complete` hoy consume el desafío de forma atómica y luego arma el PDF con `finish_pdf`. pyHanko permite, al armar la firma CMS a partir de atributos prescritos (nuestro flujo de firma externa), pasar un `timestamper` que sella el valor de la firma y lo agrega como atributo no firmado. La TSA es un servicio de red que puede fallar.

## Goals / Non-Goals

**Goals:** firmas B-T verificables con herramientas independientes; que un fallo de la TSA no destruya una firma ya hecha en el token; política clara y configurable ante el fallo.

**Non-Goals:** B-LT/B-LTA, credenciales de TSA (ver proposal).

## Decisions

1. **Sellar la firma, no el documento.** El sello de tiempo de una firma PAdES B-T es el `signature-time-stamp-token` sobre el valor de la firma. pyHanko lo hace con `async_sign_prescribed_attributes(..., timestamper=…)`, que es exactamente nuestro paso `finish`. Alternativa descartada: un sello de documento (DocTimeStamp) aparte: es B-LTA y agrega otra revisión al PDF.
2. **El cliente HTTP es el de pyHanko (`HTTPTimeStamper`)**, con tiempo límite configurable. Las pruebas usan `DummyTimeStamper` (una TSA local con su propia clave) y, para el camino HTTP real, un servidor local que responde con ese sellador: no se depende de una TSA pública.
3. **Armar el PDF antes de consumir el desafío.** Hasta ahora el consumo atómico iba primero. Si la TSA falla *después* de consumir, la firma del token (con PIN) se pierde. Se invierte el orden: primero `finish_pdf` + verificación (solo CPU y red, sin estado), después el consumo atómico. La seguridad no cambia: dos `complete` concurrentes pueden ambas armar un PDF, pero solo una gana el `UPDATE … WHERE consumed_at IS NULL`; la otra recibe `409` y descarta el suyo. Un fallo al armar el PDF sigue marcando la solicitud `failed`.
4. **Política ante TSA caída: configurable, con `false` por defecto.** Para una demostración y para sistemas donde la firma no puede bloquearse, un sello ausente es mejor que ninguna firma, y el nivel y el evento `timestamp_unavailable` dejan constancia honesta (`B-B`). Para quien exige B-T (por norma interna), `FIRMADOC_TSA_REQUIRED=true` responde `503` y deja reintentar. Siempre se informa el nivel alcanzado; nunca se declara `B-T` sin sello.
5. **Qué cuenta como "TSA no disponible"**: cualquier excepción al pedir el sello (red, tiempo agotado, respuesta con error o malformada, sello que no valida). Se separa de otros fallos al armar el PDF envolviendo solo la obtención del sello; así un PDF defectuoso no se confunde con una TSA caída.
6. **Verificación**: `trusted` del sello usa las mismas anclas que la firma (carpeta de confianza). La TSA institucional se agrega como ancla desde el panel de administración. Una firma con sello no confiable no es `ok`: un sello de una TSA desconocida no prueba nada sobre la fecha. Una firma sin sello sigue siendo `ok` (puede haberse emitido antes de configurar la TSA).
7. **`503` y `Retry-After`**: se agrega `ServiceUnavailable` (503) al conjunto de errores de dominio.

## Risks / Trade-offs

- Reordenar `complete` toca la parte más delicada del flujo; se cubre con las pruebas de concurrencia y de desafíos existentes más las nuevas de la TSA.
- Con la política opcional, dos firmas del mismo día pueden tener niveles distintos si la TSA tuvo una caída; `verify` y el nivel de cada versión lo muestran.
- La hora declarada por el firmante (`signer_reported_dt`) sigue sin ser confiable; solo la del sello lo es.
