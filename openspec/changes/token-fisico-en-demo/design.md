## Context

Ver `proposal.md` («Why»). Estado actual que condiciona el diseño:

- `demo.prepare()` escribe en `os.environ` las variables del servidor, entre ellas `FIRMADOC_PANEL_SIGNER_NAME/IDENTIFIER/EMAIL` con las constantes de `demo_pki`. El panel Angular no permite indicar un firmante al cargar un PDF: toma el de `Settings`. Por eso el CUIL del firmante del panel debe decidirse al arrancar la demo.
- `demo_pki.ensure_trust_dir()` ya copia los `.crt/.pem/.cer` de `backend/trust/` al directorio de confianza de la demo. Hoy `backend/trust/` solo tiene un README.
- El agente en modo PKCS#11 lee `%APPDATA%\FirmadocAgent\config.json` (`pkcs11_module`, `allowed_origins`); `--origin` y `--port` de la línea de comandos reemplazan a los del archivo. El `diagnose` con el token de referencia ya funciona: biblioteca cargada, certificado listado, `serialNumber` = `CUIL nnnnnnnnnnn`.
- La cadena del certificado real es: firmante → «Autoridad Certificante de Firma Digital» (ONTI, 2026-2036) → «AC Raíz de la República Argentina» (2016-2036). La raíz se obtuvo por la AIA de la intermedia (`http://acraiz.gov.ar/acraizca.cer`) y se confirmó por el enlace oficial de argentina.gob.ar (`https://acraiz.gov.ar/acraizra.crt`): misma huella.
- Confidencialidad del proyecto: el repositorio no nombra al fabricante del token, al organismo ni a personas.

## Goals / Non-Goals

**Goals:**
- Que una demo recién clonada firme con el token físico de referencia en tres pasos: middleware + `config.json`, `python -m firmadoc.demo --cuil ... --nombre ...`, agente con `--config`.
- Que las anclas de la IFDRA viajen con el repo y queden verificables (huellas en el README y en un test).
- Cero cambios en el agente, el widget y la API.

**Non-Goals:**
- Hacer configurable el firmante del panel desde la UI (eso es otra historia: hoy el panel firma «como» el operador configurado).
- Revocación en `hard-fail` o con CRL locales de la AC ONTI.
- Un instalador que escriba `config.json` con la ruta de la DLL del token de referencia.

## Decisions

1. **Parámetros de línea de comandos (`--cuil`, `--nombre`, `--email`) en lugar de respetar variables de entorno ya definidas.**
   Alternativa descartada: `os.environ.setdefault(...)` para `FIRMADOC_PANEL_SIGNER_*`. Es menos código, pero en PowerShell exigiría tres `$env:` antes del comando y la guía no sabría si el valor vino del usuario o de un entorno viejo. Los flags son explícitos, validables (11 dígitos) y se imprimen en la guía. `prepare()` recibe un `PanelSigner | None`; `main()` arma el objeto y falla con `DemoError` antes de tocar el disco si los flags son incoherentes.

2. **El token de software y su AC se siguen generando aunque haya firmante real.** Así el camino con token de software no cambia y `--reset` sigue siendo la única forma de borrar `data/demo/`. Solo cambia a quién firma el panel.

3. **Correo por defecto `<cuil>@invalid`.** El correo del firmante no interviene en la validación del certificado; `@invalid` ya es la convención de `Settings` para el operador del panel. Evita inventar un dominio.

4. **La guía imprime los dos comandos del agente (software y PKCS#11) siempre, no solo cuando hay firmante real.** La ruta `config.json` se muestra con `%APPDATA%` literal (sin expandir) para que el comando sea copiable en cualquier PC, y se agrega una línea aclarando que con token físico el PIN es el del token. El bloque con el firmante configurado dice «token de prueba» o «token físico» según el caso.

5. **Anclas en PEM, un certificado por archivo, con nombres descriptivos:** `backend/trust/ac-raiz-republica-argentina-2016.crt` y `backend/trust/ac-firma-digital-onti-2026.crt`. PEM es lo que acepta `trust.py` y lo que muestra el panel `/admin`; un certificado por archivo permite quitarlos por separado desde `DELETE /trust-anchors/{fingerprint}` (que rechaza archivos con varios certificados). El README lista las huellas, las URL oficiales y el comando `openssl x509 -noout -fingerprint -sha256`.

6. **Test de anclas sin red:** `tests/test_trust_repo.py` carga `backend/trust/` con `load_trust_store`, comprueba una raíz y una intermedia con las huellas esperadas, que la intermedia esté firmada por la raíz, y que una cadena de prueba firmada por la intermedia valide con `CertificateChecker(..., revocation_mode="soft-fail", allow_fetching=False)`. Para no incluir una clave privada de la AC ONTI (no existe tal cosa), la prueba de cadena usa el certificado de la intermedia como hoja contra la raíz: `_chain_only` acepta cualquier certificado cuyo emisor esté en las anclas.

7. **Documentación sin nombres propios.** Se escribe «token criptográfico USB de referencia», «biblioteca PKCS#11 del fabricante (64 bits)» y «titular del certificado». La ruta de la DLL aparece solo como ejemplo genérico `C:\Windows\System32\<biblioteca-del-fabricante>.dll`, como hasta ahora.

## Risks / Trade-offs

- [El servidor intenta descargar la CRL de la AC ONTI en `soft-fail` con `FIRMADOC_REVOCATION_FETCH=true`; si la red lo bloquea, la validación sigue (indeterminada) pero puede tardar] → documentar en `docs/demo.md` que se puede poner `FIRMADOC_REVOCATION_FETCH=false` para la demo.
- [La intermedia de la ONTI se renueva (la actual es de 2026); el archivo quedaría viejo] → el README indica cómo agregar una nueva desde `/admin` o copiándola; el test verifica huellas exactas, así que una renovación obliga a actualizar test y README a conciencia.
- [Un CUIL de 11 dígitos sintácticamente válido pero distinto al del certificado] → el servidor responde `cuil_mismatch` como hoy; la guía recuerda que el CUIL debe ser el del `diagnose`.
- [Chrome 142+ pide permiso de red local para llegar a `127.0.0.1`] → ya documentado en `agent/README.md`; se enlaza desde `docs/demo.md`.

## Migration Plan

Sin migraciones ni cambios de configuración obligatorios: quien no pase los flags nuevos no nota diferencia. Las anclas nuevas en `backend/trust/` entran en el directorio de confianza de la demo en el siguiente arranque (se copian en `prepare`). Rollback: borrar los dos `.crt` y revertir el commit.

## Open Questions

- Si la validación con revocación `soft-fail` contra `http://pki.jgm.gov.ar/crl/FD.crl` resulta lenta en la red de la usuaria, se decidirá al probar si la demo fija `FIRMADOC_REVOCATION_FETCH=false` por defecto. No cambia specs ni tareas: es un valor de entorno documentado.
