"""Prueba manual con un token físico: lista el certificado, firma un lote con UN solo PIN y verifica.

Uso (PowerShell):
    python agent/scripts/manual_token_test.py --module "C:\\Windows\\System32\\eTPKCS11.dll"

El PIN se pide por consola sin mostrarlo (o se toma de FIRMADOC_TEST_PIN en pruebas automáticas).
ATENCIÓN: un PIN incorrecto cuenta contra el límite de intentos del token. El script hace UN único
intento y no reintenta.
"""

import argparse
import getpass
import os
import sys

from firmadoc_agent.errors import AgentError
from firmadoc_agent.pkcs11_backend import Pkcs11Backend
from firmadoc_agent.selftest import self_test


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--module", required=True, help="ruta de la biblioteca PKCS#11 del fabricante")
    parser.add_argument("--certificate-id", help="id del certificado (de `firmadoc-agent diagnose`)")
    parser.add_argument("--batch", type=int, default=3, help="hashes del lote (por defecto 3)")
    args = parser.parse_args()

    pin = os.environ.get("FIRMADOC_TEST_PIN") or getpass.getpass("PIN del token (un solo intento): ")
    try:
        ok = self_test(Pkcs11Backend(args.module), pin, args.certificate_id, args.batch)
    except AgentError as e:
        print(f"FALLO [{e.code}]: {e.detail}")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
