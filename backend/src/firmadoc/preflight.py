"""Verificación previa de la configuración. Uso: `python -m firmadoc.preflight`.

En modo real los errores impiden arrancar; en modo demostración los mismos hallazgos son advertencias.
Es una función pura sobre la configuración (y la carpeta de confianza): sin red ni base de datos.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .certificate_validation import load_crls
from .config import Settings, get_settings
from .trust import _read_directory

ERROR, WARNING, INFO = "error", "warning", "info"


@dataclass(frozen=True)
class Finding:
    level: str
    code: str
    message: str


def check(settings: Settings) -> list[Finding]:
    real = settings.real_mode
    out: list[Finding] = []

    def problem(code: str, message: str) -> None:
        out.append(Finding(ERROR if real else WARNING, code, message))

    def warn(code: str, message: str) -> None:
        out.append(Finding(WARNING, code, message))

    if not settings.signing_secret:
        problem("signing_secret_missing", "falta FIRMADOC_SIGNING_SECRET (secreto de los enlaces del widget)")
    if settings.revocation_mode != "hard-fail":
        problem(
            "revocation_not_strict",
            f"FIRMADOC_REVOCATION_MODE es '{settings.revocation_mode}': debe ser 'hard-fail' "
            "(con otro valor un certificado revocado puede pasar si falla la consulta)",
        )
    elif not settings.revocation_fetch and not load_crls(settings.crl_dir):
        problem(
            "revocation_no_source",
            "la revocación es 'hard-fail' pero no hay fuente: habilitar FIRMADOC_REVOCATION_FETCH "
            "o cargar CRL en FIRMADOC_CRL_DIR",
        )
    store = _read_directory(Path(settings.trust_dir))
    if not store.roots:
        problem("no_trust_anchors", f"no hay ninguna ancla raíz en '{settings.trust_dir}' (FIRMADOC_TRUST_DIR)")
    if settings.firmar_mock_enabled:
        problem("mock_enabled", "FIRMADOC_FIRMAR_MOCK_ENABLED=true: el servicio de firma remota simulado está activo")
    if settings.webhook_allow_http or settings.webhook_allow_private_hosts:
        problem("webhooks_unsafe", "los webhooks permiten http o hosts privados (solo para desarrollo)")

    if settings.database_url.startswith("sqlite"):
        warn("sqlite", "la base es SQLite: para operar usar PostgreSQL (docs/database.md)")
    host = urlsplit(settings.public_base_url)
    if host.scheme != "https" and host.hostname not in ("localhost", "127.0.0.1"):
        warn("public_url_not_https", "FIRMADOC_PUBLIC_BASE_URL no usa https")
    if not settings.admin_token:
        warn("admin_disabled", "la administración está deshabilitada (falta FIRMADOC_ADMIN_TOKEN)")
    if settings.storage_backend == "files":
        warn("storage_files", "los PDF se guardan en disco: para que queden en la base, FIRMADOC_STORAGE_BACKEND=database")
    if real:
        out.append(Finding(INFO, "local_disabled", "modo real: el proveedor 'local' (demostración) no está habilitado"))
    return out


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.level == ERROR]


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    findings = check(settings)
    print(f"Modo: {'REAL' if settings.real_mode else 'demostración'}")
    for f in findings:
        print(f"  [{f.level.upper()}] {f.code}: {f.message}")
    bad = errors(findings)
    print("Resultado: " + (f"{len(bad)} error(es): no se puede operar" if bad else "sin errores"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
