# backend/trust/

Anclas de confianza: certificados raíz y de AC (`.crt` o `.pem`) con los que se validan los
certificados de los firmantes (proveedor `token`).

- Los certificados **autofirmados** se tratan como raíces; el resto, como AC intermedias.
- Descargar siempre desde la **fuente oficial de la AC** y confirmar la huella por un canal
  independiente: `python -m firmadoc.trust list` muestra el sujeto y la huella SHA-256 de cada uno.
- Solo van certificados públicos. No guardar claves privadas aquí (`*.key` está en `.gitignore`).
- Sin ningún ancla cargada, todo certificado de tercero se rechaza como no confiable.

## Anclas incluidas: infraestructura de firma digital de la República Argentina

El repositorio trae la cadena que usan los certificados de firma digital emitidos por la ONTI
(un certificado por archivo, en PEM):

| Archivo | Sujeto | Vigencia | Huella SHA-256 | Fuente oficial |
|---|---|---|---|---|
| `ac-raiz-republica-argentina-2016.crt` | AC Raíz de la República Argentina (raíz, autofirmada) | 2016-06-30 a 2036-06-30 | `975c663546ed8923d132256f2f3300838e3fe01e04e37739e954ff931e9f8ba4` | `https://acraiz.gov.ar/acraizra.crt` (enlazado desde la página de la AC Raíz en argentina.gob.ar) y `http://acraiz.gov.ar/acraizca.cer` (AIA de la intermedia) |
| `ac-firma-digital-onti-2026.crt` | Autoridad Certificante de Firma Digital (ONTI), emitida por la raíz | 2026-08-03 a 2036-06-30 | `b3c367a4e3842854c8820a9eda492318e2ca0ecf9abb8130de8f6dcd53ac2510` | `http://pki.jgm.gov.ar/aia/cafdONTI(2).crt` (AIA de los certificados de usuario) |

La raíz se descargó por dos caminos (la AIA de la intermedia y el enlace de la página oficial) y las
dos copias tienen la misma huella. Para recalcular una huella y compararla con la tabla:

```powershell
openssl x509 -in backend\trust\ac-raiz-republica-argentina-2016.crt -noout -fingerprint -sha256
```

`tests/test_trust_repo.py` comprueba que estos dos archivos sigan aquí, con esas huellas, y que la
intermedia esté firmada por la raíz. Si la ONTI renueva la intermedia, agregar la nueva como otro
archivo (o desde el panel `/admin` → Confianza), actualizar esta tabla y el test, y conservar la
anterior mientras haya certificados vigentes emitidos por ella.
