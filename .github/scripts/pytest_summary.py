"""Resume un informe JUnit de pytest en Markdown, para el resumen de la ejecución del pipeline.

Uso: python .github/scripts/pytest_summary.py "<título>" <informe.xml> >> "$GITHUB_STEP_SUMMARY"

Si el informe no existe (la suite no llegó a correr) lo dice, en lugar de mostrar un resumen vacío.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def summary(title: str, report: Path) -> str:
    if not report.exists():
        return f"### {title}\n\nNo hay informe de pruebas: la suite no llegó a ejecutarse.\n"
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = sum(int(s.get("tests", 0)) for s in suites)
    failed = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    seconds = sum(float(s.get("time", 0)) for s in suites)
    passed = total - failed - skipped
    lines = [
        f"### {title}",
        "",
        "| Aprobadas | Fallidas | Omitidas | Total | Duración |",
        "|---:|---:|---:|---:|---:|",
        f"| {passed} | {failed} | {skipped} | {total} | {seconds:.0f} s |",
        "",
    ]
    if total == 0:
        lines.append("**Atención:** no se ejecutó ninguna prueba; un nivel vacío no es un nivel que pasa.")
    elif skipped:
        lines.append("Las omitidas dependen de algo que este trabajo no tiene (ver docs/ci.md).")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(summary(sys.argv[1], Path(sys.argv[2])))
