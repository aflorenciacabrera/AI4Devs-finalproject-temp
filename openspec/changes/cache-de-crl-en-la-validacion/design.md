## Context

Ver `proposal.md`. Hechos que condicionan el diseño:

- `CertificateChecker` se construye por pedido (`providers._token(settings)` no cachea), así que una caché por instancia no serviría: tiene que vivir a nivel de módulo, con un lock (el servidor atiende hilos).
- `CertificateChecker._context()` crea un `ValidationContext` de pyHanko por validación, con `crls=` para CRL locales. Tras validar, `ValidationContext.crls` expone todas las CRL que conoce (locales más las descargadas) como objetos `asn1crypto.crl.CertificateList`. Medido con la CRL real: pasar el objeto ya parseado o los bytes cuesta lo mismo (~2 s); la descarga es lo que varía (1,5 a 41 s).
- pyHanko, con una CRL local vigente que cubre al emisor, no vuelve a descargarla (medido: 6 s con red permitida contra 5 s sin red, con cuatro CRL en memoria).
- Las CRL de `FIRMADOC_CRL_DIR` se leen en `providers._token` y llegan como `crls` del checker.

## Goals / Non-Goals

**Goals:**
- Una descarga de CRL por proceso y por período de vigencia; el resto de las validaciones en ~2 s.
- Sin cambios de comportamiento observable salvo el tiempo: mismos códigos, misma revalidación en `complete`.

**Non-Goals:**
- Persistencia en disco o compartida entre procesos (varios workers de uvicorn tendrían cada uno su caché; aceptable).
- Caché de respuestas OCSP (el de la AC responde 500; pyHanko ya cae a CRL).

## Decisions

1. **`CrlCache` a nivel de módulo en `certificate_validation.py`**, con `threading.Lock`, diccionario `sha256(dump) → CertificateList`. Métodos: `fresh(now) -> list[CertificateList]` (descarta y purga las vencidas por `next_update`; una CRL sin `next_update` se considera vigente) y `add(crls)` (ignora duplicados por huella). Alternativa descartada: reutilizar un único `ValidationContext` de larga vida; pyHanko fija `moment` al crearlo y guarda estado de validación, no está pensado para compartirse entre pedidos.
2. **Integración mínima en el checker:** `_context()` pasa `crls = self.crls + CRL_CACHE.fresh(now)`; `_run()` conserva el contexto y, si `allow_fetching`, llama a `CRL_CACHE.add(ctx.crls)` al terminar (también cuando la validación falla: la CRL descargada sirve igual). Las CRL de `FIRMADOC_CRL_DIR` y las cacheadas van juntas; si hay dos vigentes para el mismo emisor, pyHanko elige por fechas.
3. **El checker acepta `crls` como bytes o como `CertificateList`** (pyHanko admite ambos), para no serializar y volver a parsear 9 MB en cada contexto.
4. **Pruebas sin red** con la PKI de prueba: (a) un checker con `crls=[crl de prueba]` y `allow_fetching=True` valida y alimenta la caché; otro checker sin `crls` y `allow_fetching=False` rechaza el certificado revocado gracias a la caché; (b) una CRL con `next_update` en el pasado no se entrega; (c) `add` de la misma CRL dos veces deja una entrada. Fixture `autouse` que limpia la caché entre pruebas para no acoplarlas.
5. **Observabilidad:** un `log.info` cuando la caché incorpora una CRL nueva (emisor, `next_update`, tamaño), para que en el registro del servidor se vea cuándo se descargó.

## Risks / Trade-offs

- [Memoria: una CRL de 9 MB por AC, más su parseo] → es una por AC y por período; aceptable para un servicio de firma. Las vencidas se purgan en cada `fresh()`.
- [Un certificado revocado hoy no aparece hasta la próxima CRL] → ya era así: la CRL se publica con `next_update` diario; la caché respeta ese plazo y no agrega retraso.
- [Varios workers: cada proceso descarga la suya] → documentado; `FIRMADOC_CRL_DIR` sigue disponible para compartir por disco.
- [La primera validación después de arrancar sigue tardando lo que tarde la red] → documentado en `docs/demo.md`; el tiempo de espera del widget se amplía en paralelo (otra tarea).

## Migration Plan

Sin configuración nueva ni migraciones. Rollback: revertir el commit.
