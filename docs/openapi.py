"""Exporta el contrato OpenAPI de Firmadoc a docs/openapi.json.

Uso (desde la raíz del repositorio, con el entorno virtual activo):

    python docs/openapi.py

El contrato sale de la aplicación FastAPI (rutas y esquemas pydantic), no se edita a mano. Con el servidor
levantado, el mismo contrato se sirve en /openapi.json y se navega en /docs.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / "openapi.json"
sys.path.insert(0, str(ROOT / "backend" / "src"))

from firmadoc.main import app

if __name__ == "__main__":
    OUT.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(app.openapi()['paths'])} rutas")
