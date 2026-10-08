"""Atajo para `firmadoc-agent diagnose` (lista certificados y verifica la biblioteca PKCS#11)."""

import sys

from firmadoc_agent.__main__ import main

if __name__ == "__main__":
    sys.exit(main(["diagnose", *sys.argv[1:]]))
