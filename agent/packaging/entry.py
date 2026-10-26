"""Punto de entrada para PyInstaller (el paquete usa imports relativos, así que no se empaqueta
`__main__.py` directamente)."""

import sys

from firmadoc_agent.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
