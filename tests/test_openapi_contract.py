"""El contrato OpenAPI versionado (docs/openapi.json) no se queda atrás respecto de la aplicación."""

import json
from pathlib import Path

from firmadoc.main import app

CONTRACT = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def _operations(spec: dict) -> set[tuple[str, str]]:
    return {(path, method) for path, item in spec["paths"].items() for method in item}


def test_el_contrato_versionado_cubre_todas_las_rutas():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    missing = _operations(app.openapi()) - _operations(contract)
    assert not missing, f"regenerar con `python docs/openapi.py`: faltan {sorted(missing)}"


def test_el_contrato_incluye_la_carga_desde_el_panel():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert "post" in contract["paths"]["/api/v1/admin/signing-uploads"]
    assert "post" in contract["paths"]["/api/v1/admin/signing-batch-uploads"]
