"""`firmadoc-agent diagnose`: verifica la biblioteca PKCS#11 y lista los certificados del token.

Nunca pide el PIN ni abre una sesión autenticada: solo lee objetos públicos.
"""

import platform
import struct
from collections.abc import Callable

from cryptography import x509

from . import __version__
from .backend import TokenBackend
from .certs import key_usage_text, subject_serial_number
from .config import AgentConfig
from .errors import AgentError

EXIT_OK = 0
EXIT_LIBRARY = 1
EXIT_NO_TOKEN = 2


def run_diagnose(
    config: AgentConfig, backend: TokenBackend, out: Callable[[str], None] = print
) -> int:
    out(f"Firmadoc Agent {__version__}")
    out(f"Python {platform.python_version()} de {struct.calcsize('P') * 8} bits ({platform.system()})")
    out(f"Biblioteca PKCS#11 configurada: {config.pkcs11_module or '(sin configurar)'}")
    out("Este diagnóstico no pide el PIN ni abre sesión autenticada.")
    out("")

    try:
        tokens = backend.inspect()
    except AgentError as e:
        out(f"ERROR [{e.code}]: {e.detail}")
        if e.code == "pkcs11_unavailable":
            out(
                "Sugerencias: verifique la ruta de 'pkcs11_module' y que la biblioteca sea de la "
                "misma arquitectura (32 o 64 bits) que este agente; instale el middleware del "
                "fabricante del token."
            )
            return EXIT_LIBRARY
        return EXIT_NO_TOKEN
    except Exception as e:  # noqa: BLE001 - el diagnóstico nunca debe terminar con una traza
        out(f"ERROR inesperado al consultar el token: {e}")
        return EXIT_LIBRARY

    out("Biblioteca PKCS#11 cargada correctamente.")
    if not tokens:
        out("No hay ningún token conectado (o está sin inicializar).")
        return EXIT_NO_TOKEN

    for token in tokens:
        out(f"Token: {token.label}  (fabricante: {token.manufacturer}, modelo: {token.model})")
        out(f"  Número de serie: {token.serial}")
        out(f"  Indicadores: {', '.join(token.flags) or '-'}")
        if not token.certificates:
            out("  Sin certificados.")
        for cert, ca in token.certificates:
            parsed = x509.load_der_x509_certificate(cert.der)
            out(f"  - Certificado {'de AC' if ca else 'de usuario'}  (id: {cert.id})")
            out(f"      Sujeto:   {cert.subject}")
            out(f"      Emisor:   {cert.issuer}")
            out(f"      Serie:    {cert.serial_number}")
            out(f"      Vigencia: {cert.not_before:%Y-%m-%d} a {cert.not_after:%Y-%m-%d}")
            out(f"      Uso de clave: {key_usage_text(parsed)}")
            if not ca:
                raw = subject_serial_number(parsed)
                out(f"      serialNumber del sujeto (CUIL): {raw if raw else '(no tiene)'}")
    out("")
    out("Diagnóstico completo.")
    return EXIT_OK
