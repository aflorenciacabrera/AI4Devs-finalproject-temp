# backend/trust/

Anclas de confianza: certificados raíz y de AC (`.crt` o `.pem`) con los que se validan los
certificados de los firmantes (proveedor `token`).

- Los certificados **autofirmados** se tratan como raíces; el resto, como AC intermedias.
- Descargar siempre desde la **fuente oficial de la AC** y confirmar la huella por un canal
  independiente: `python -m firmadoc.trust list` muestra el sujeto y la huella SHA-256 de cada uno.
- Solo van certificados públicos. No guardar claves privadas aquí (`*.key` está en `.gitignore`).
- Sin ningún ancla cargada, todo certificado de tercero se rechaza como no confiable.
