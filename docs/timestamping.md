# Sello de tiempo (PAdES B-T)

El sello de una autoridad de sellado de tiempo (TSA, RFC 3161) prueba **cuándo** se firmó con una fecha en la que
se puede confiar. Sin TSA, las firmas son PAdES B-B (la hora la declara el firmante o el servidor).

## Configuración

| Variable | Significado | Por defecto |
|---|---|---|
| `FIRMADOC_TSA_URL` | URL `http://` o `https://` de la TSA. Vacía = sin sello | vacía |
| `FIRMADOC_TSA_TIMEOUT_SECONDS` | Tiempo límite del pedido | `10` |
| `FIRMADOC_TSA_REQUIRED` | `true`: sin sello no se firma | `false` |

## Comportamiento de `complete`

1. Se arma el PDF firmado y se pide a la TSA el sello **de la firma** (no del documento).
2. Recién después se consume el desafío de un solo uso. Si la TSA falla, no se gasta la firma hecha en el token.

| Situación | Resultado |
|---|---|
| Sin `FIRMADOC_TSA_URL` | Firma `B-B`; el evento `signed` registra `timestamp: absent` |
| TSA responde | Firma `B-T`; `timestamp: embedded` |
| TSA caída, sello opcional | Firma `B-B`; `timestamp: unavailable` y evento `timestamp_unavailable` con el motivo |
| TSA caída, sello obligatorio | `503` con `code: timestamp_unavailable`; la solicitud sigue en `signing` y se puede **reintentar `complete`** con la misma firma (sin otro PIN) |

El nivel de cada versión (`signature_level`) y el webhook reflejan lo que realmente se logró; nunca se declara
`B-T` sin sello.

## Confianza en la TSA

`POST /api/v1/documents/{id}/verify` informa por firma `timestamp.present`, `time`, `intact`, `valid` y
`trusted`. El sello es de confianza si la cadena de la TSA llega a un ancla de `FIRMADOC_TRUST_DIR`: agregar
la raíz de la TSA institucional desde el panel de administración (`docs/admin.md`). Una firma con un sello de
una TSA desconocida **no** es `ok`.

## Verificación independiente

```
openssl ts -verify -in token.der -token_in -digest <sha256-de-la-firma> -CAfile raiz.pem -untrusted ac.pem
```

(el token es el atributo `signature-time-stamp-token` de la firma CMS; la prueba `tests/test_timestamping.py`
lo hace con `openssl`).

## Límites

- No incluye B-LT / B-LTA (revocación incrustada y sellos de archivo); es una evolución.
- La TSA se configura por URL sin credenciales.
