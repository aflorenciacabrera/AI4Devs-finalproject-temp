# Prototipo de referencia: firma digital con token (investigación previa)

> **Estado de este documento:** redactado a partir del texto de una conversación compartida con un asistente de IA. **El código fuente no fue revisado ni ejecutado** (el archivo `firma-digital.zip` no es accesible desde el enlace compartido). Todo lo marcado como "según la conversación" es una afirmación de esa fuente, no una verificación propia. Se actualizará cuando se obtenga el `.zip` (ver sección 8).

## 1. Origen, alcance y atribución

- **Origen:** conversación compartida (https://claude.ai/share/4eaaf54e-179a-429f-ac04-9485cfecca36) de un compañero de trabajo con un asistente de IA, sobre cómo implementar firma digital con token en una aplicación web con backend Python y PCs Windows.
- **Uso en Firmadoc:** insumo de investigación para el diseño (firma diferida, agente local, validación de confianza). **No se reutilizó código.** Si en la Entrega 2 se reutiliza o adapta algún fragmento del prototipo, debe indicarse expresamente su origen y contar con la conformidad de su autor.
- **Confidencialidad:** este documento no nombra al organismo, la provincia ni los proveedores comerciales involucrados.

## 2. Qué contiene el prototipo (según la conversación)

| Archivo / carpeta | Función según la conversación |
|---|---|
| `servidor/firma.py` | Núcleo con `preparar()` y `completar()` sobre pyHanko. No depende de ningún framework web |
| `agente/agente.py` | Agente local para las PC: habla con el token por PKCS#11, atiende solo al origen de la aplicación y pide el PIN una vez por lote |
| `agente/diagnostico.py` | Diagnóstico sin PIN: qué biblioteca PKCS#11 cargó, mecanismos de firma que declara el token, datos del certificado (incluye si detecta el CUIL), si trae el certificado de la AC. Con `--firmar` pide el PIN una vez y hace dos firmas de prueba; con `--exportar` guarda los certificados públicos como `.crt` |
| `servidor/app_demo.py` y `firmar.js` | Demo mínima en Flask que muestra cómo se conectan servidor, página y agente |
| `servidor/revisar_confianza.py` | Usa una carpeta `confianza` con los `.crt` oficiales; muestra la huella SHA-256 de cada uno y si la cadena del firmante llega a una raíz de la carpeta |
| `pruebas/` | Generador de certificados de prueba (raíz, "AC" y firmante con CUIL, sin valor legal) y pruebas automáticas |
| `README` propio | Pasos para correr la demo sin token (unos 10 minutos, según la conversación) |

## 3. Qué se verificó y qué no (según la conversación)

**Verificado en Linux con un token de software (SoftHSM), 18 pruebas pasando:**
- La firma sale en nivel PAdES B-LT y la valida también `pdfsig` (Poppler), una herramienta independiente de pyHanko.
- Dos firmas sobre el mismo PDF no se invalidan entre sí.
- Se rechazan: certificado revocado, certificado de otra AC, CUIL que no coincide con el usuario y firma hecha con otra clave.
- El agente firma contra SoftHSM y el flujo completo corre en Chromium (con `localhost` como origen).
- Casos de tokens reales: tokens que solo firman "en crudo" (el agente calcula el hash) y claves que exigen el PIN en cada firma (el lote igual sale con un solo ingreso).

**No verificado (declarado por la propia conversación):**
- Funcionamiento con un token físico y en Windows.
- La ventana de PIN (Tkinter) no se ejecutó.
- La restricción de orígenes con el sitio publicado (la prueba usa `localhost`).
- Qué servicio de sellado de tiempo usaría el organismo (sin él la firma queda en B-B).
- Que el CUIL esté en el atributo `serialNumber` con formato "CUIL 20123456789" (es un supuesto a confirmar con un certificado real).

## 4. Decisiones técnicas relevantes

1. **Firma diferida:** el servidor prepara el PDF y calcula el hash; el token firma solo el hash; el servidor incrusta la firma. El documento no viaja a la PC y la clave privada nunca toca el servidor. *(Verificado en la documentación pública de pyHanko: "firma interrumpida", con SHA-256 sobre los atributos firmados y cierre con `async_finish_signing`.)*
2. **Qué se firma:** el hash de los atributos firmados de la estructura CMS, no el hash del PDF. Se usa la API de firma externa de la biblioteca; no se calcula a mano.
3. **Espacio reservado para la firma:** 16 a 32 KB, para que quepan firma, cadena de certificados y sello de tiempo.
4. **Varias firmas:** cada firma nueva es una actualización incremental; reescribir el PDF invalida las anteriores.
5. **Lote:** todos los hashes en una sola llamada al agente para que el PIN se pida una vez.
6. **Acceso al token:** PKCS#11 (elegido por sobre el almacén de certificados de Windows por ser más directo desde Python).
7. **Controles del agente:** escucha solo en `127.0.0.1`, acepta solo orígenes permitidos, confirma con el usuario antes de firmar y expone solo dos operaciones (listar certificados y firmar hashes).
8. **Controles del servidor:** cadena hasta la AC Raíz, vigencia y revocación al momento de firmar, CUIL del certificado = usuario autenticado, hash devuelto = documento pendiente de esa sesión.
9. **Agente en Python y no en React/Electron:** la recomendación fue no migrar, porque el agente casi no tiene interfaz y lo difícil (token y seguridad) ya está resuelto en Python.
10. **Chrome 142 o superior:** una página pública que llama a `127.0.0.1` dispara un pedido de permiso de acceso a la red local; en equipos administrados se evita con la política `LocalNetworkAccessAllowedForUrls`. *(Verificado en las notas de versión de Chrome.)*

## 5. Token de referencia (según la conversación)

Modelo: mToken CryptoID (Century Longmai), FIPS 140-3 nivel 3. Biblioteca PKCS#11: `CryptoIDA_pkcs11.dll`, instalada por el software del fabricante. La DLL debe coincidir en arquitectura (32/64 bits) con el Python del agente. PIN de 8 a 32 caracteres y bloqueo a los 15 intentos fallidos, salvo otra configuración de quien lo entregó. La política de la AC exige dispositivos FIPS 140-2 nivel 2 o superior.

## 6. Cómo se ejecutaría (comandos citados en la conversación)

Sin token (demo con certificados de prueba): seguir el README incluido en el `.zip`.

Con un token físico, en la PC con el software del fabricante instalado:
```bash
pip install -r requirements.txt
python agente/diagnostico.py                       # solo lee datos públicos, no pide PIN
python agente/diagnostico.py --firmar              # pide el PIN una vez y hace dos firmas de prueba
python agente/diagnostico.py --exportar exportados # guarda los .crt públicos
python -m servidor.revisar_confianza confianza exportados/firmante_1.crt
```
Los certificados oficiales para la carpeta `confianza` deben bajarse siempre de la página oficial de la AC, y su huella confirmarse por un canal independiente.

## 7. Relación con Firmadoc

| Prototipo | Equivalente en Firmadoc | Diferencia |
|---|---|---|
| `servidor/firma.py` (`preparar`/`completar`) | Motor PAdES + `TokenAgentProvider` y `LocalPAdESProvider` | Firmadoc agrega solicitudes, documentos, versionado, auditoría y proveedores intercambiables |
| `agente/agente.py` | `agent/` (Firmadoc Agent) | Mismo enfoque; en Firmadoc el agente solo lista certificados y firma hashes |
| `agente/diagnostico.py` | `agent/diagnostico.py` | Igual propósito |
| `servidor/revisar_confianza.py` | `backend/trust/` + servicio de validación | En Firmadoc la validación corre en cada firma y queda registrada en la auditoría |
| `servidor/app_demo.py` + `firmar.js` | Sistema integrador de prueba y widget embebible | Firmadoc se integra desde cualquier sistema (iframe/Web Component) |
| `pruebas/` | Suite de tests (sección 2.6 del README) | Se amplía con integración y end-to-end |

## 8. Pendientes cuando se obtenga el `firma-digital.zip`

- [ ] Conseguir el `.zip` con quien lo generó (descargándolo desde su conversación original) y su conformidad para usarlo como referencia.
- [ ] Leer el código y confirmar la estructura de la sección 2 (nombres de archivos y funciones).
- [ ] Ejecutar las pruebas y la demo; anotar versiones de Python y dependencias.
- [ ] Verificar los puntos de la sección 3 "no verificado" con un token físico, o dejarlos como riesgo explícito.
- [ ] Decidir qué se reutiliza, qué se reescribe y cómo se atribuye, y reflejarlo en `prompts.md`.

## 9. Referencias

- Documentación de pyHanko, firma interrumpida: https://docs.pyhanko.eu/en/latest/lib-guide/signing.html
- Notas de versión de Chrome 142 (Local Network Access): https://developer.chrome.com/release-notes/142
- Villanueva y Molinari (2021), plataforma de firma digital para aplicaciones web de un poder judicial provincial: http://sedici.unlp.edu.ar/handle/10915/141553
