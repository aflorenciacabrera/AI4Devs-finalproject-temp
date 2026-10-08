# backend/

API de Firmadoc (FastAPI + SQLAlchemy + Alembic). Código en `src/firmadoc/`, migraciones en `migrations/`.

## Desarrollo

```bash
python -m venv .venv && .venv/Scripts/activate   # Windows (Git Bash: source .venv/Scripts/activate)
pip install -e ".[dev]"
alembic upgrade head                              # SQLite local por defecto
python -m firmadoc.seed                           # datos de demo
uvicorn firmadoc.main:app --reload
```

Base de datos: variable `FIRMADOC_DATABASE_URL` (ver `.env.example`).

## Tests

```bash
pytest                                            # SQLite
docker compose up -d postgres
FIRMADOC_TEST_PG_URL=postgresql+psycopg://firmadoc:firmadoc@localhost:5432/firmadoc pytest   # + PostgreSQL
```

Los tests de PostgreSQL recrean el esquema `public`: usar una base descartable.

## Recorrer el flujo de firma (proveedor `local`)

Con la base migrada, el seed aplicado y la API en marcha (`uvicorn firmadoc.main:app`), usando la API key de demo `firmadoc-demo-key`:

```bash
H='X-API-Key: firmadoc-demo-key'
B=$(base64 -w0 documento.pdf)

# 1. crear la solicitud (devuelve id, document_id y signing_url)
curl -s -X POST localhost:8000/api/v1/signature-requests -H "$H" -H 'Content-Type: application/json' \
  -d "{\"document_base64\":\"$B\",\"provider\":\"local\",\"signer\":{\"full_name\":\"Ana\",\"identifier\":\"20111111112\",\"email\":\"ana@example.org\"}}"

# 2. preparar: devuelve el hash a firmar (desafío de un solo uso, vence en 5 min)
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/prepare -H "$H"

# 3. completar: para `local` el servidor firma el hash; devuelve la versión 2 vigente y descargable
curl -s -X POST localhost:8000/api/v1/signature-requests/$ID/complete -H "$H"

# 4. descargar una versión
curl -s -o firmado.pdf localhost:8000/api/v1/documents/$DOC/versions/2/download -H "$H"
```

Notas:
- `X-Session-Ref` (opcional) ata el desafío a una sesión; `complete` debe enviar el mismo valor.
- `provider` `token` y `firmar` responden `422` hasta que se implementen.
- `callback_url` se acepta pero todavía no se usa (los webhooks son FIRDOC-24).
- La firma de `local` es **electrónica** (certificado autofirmado de demostración, nivel PAdES B-B). El certificado y su clave se generan en `FIRMADOC_LOCAL_CERT_DIR` (`data/` está fuera de git).

## Firma con token (proveedor `token`)

El servidor valida el certificado público del token y verifica las firmas de los hashes; la clave privada y el PIN nunca llegan a Firmadoc. El contrato con el agente local está en [`docs/agent-contract.md`](../docs/agent-contract.md).

Configuración (variables de entorno, ver `.env.example`):

| Variable | Por defecto | Uso |
|---|---|---|
| `FIRMADOC_TRUST_DIR` | `backend/trust` | anclas de confianza (`.crt`/`.pem`): raíces y ACs intermedias de los certificados de los firmantes |
| `FIRMADOC_REVOCATION_MODE` | `soft-fail` | `hard-fail` rechaza si no se puede verificar la revocación; `soft-fail` acepta con estado `unknown`; `off` no consulta |
| `FIRMADOC_REVOCATION_FETCH` | `true` | consultar CRL/OCSP por red |
| `FIRMADOC_CRL_DIR` | — | CRLs locales (`.crl`/`.der`), útil sin salida a internet |

Cargar las anclas **desde la fuente oficial de la AC** y confirmar su huella por otro canal:

```bash
python -m firmadoc.trust list      # sujeto y huella SHA-256 de cada ancla cargada
```

Sin anclas cargadas, todo certificado de tercero se rechaza como `certificate_untrusted`. Los rechazos devuelven `{"detail", "code"}` (`certificate_untrusted`, `certificate_expired`, `certificate_revoked`, `certificate_invalid`, `cuil_mismatch`).

Los tests recorren el flujo completo con un **simulador de agente** (`tests/agent_simulator.py`) y una PKI de prueba (`tests/pki.py`), sin hardware ni valor legal.

## Webhooks

Aviso al integrador al firmar o fallar una solicitud: ver [`docs/webhooks.md`](../docs/webhooks.md).
Alta de integradores: `python -m firmadoc.integrators --help`.
