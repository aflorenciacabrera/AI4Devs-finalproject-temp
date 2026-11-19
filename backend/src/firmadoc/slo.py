"""Mide el SLO de firma a partir de los registros estructurados (docs/slo/api.md).

Uso: `python -m firmadoc.slo [--objective 99] [--latency-ms 3000] [--fail-on-breach] [archivo ...]`
Lee líneas JSON (las que escribe `firmadoc.observability`) de los archivos o de la entrada estándar; las
líneas que no son JSON se ignoran. Cuenta los pedidos de firma (`prepare` y `complete`, individuales y en
lote, del integrador y del widget) y calcula los dos indicadores, el presupuesto de error consumido y la
tasa de consumo en la ventana que cubren esos registros.
"""

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass

SIGNING_SUFFIXES = ("/prepare", "/complete")
MIN_SAMPLE = 100  # con menos pedidos, un solo error mueve el porcentaje varios puntos


@dataclass
class Sli:
    total: int = 0
    bad: int = 0

    @property
    def good_ratio(self) -> float:
        return 1.0 if self.total == 0 else (self.total - self.bad) / self.total

    def burn_rate(self, objective: float) -> float:
        """Cuántas veces más rápido de lo sostenible se consume el presupuesto (1 = justo el objetivo)."""
        budget = 1 - objective
        return 0.0 if self.total == 0 else (self.bad / self.total) / budget


@dataclass
class Report:
    availability: Sli
    latency: Sli
    objective: float
    latency_ms: float

    @property
    def breached(self) -> bool:
        return self.availability.good_ratio < self.objective or self.latency.good_ratio < self.objective


def is_signing_request(entry: dict) -> bool:
    return entry.get("event") == "http_request" and str(entry.get("route", "")).endswith(SIGNING_SUFFIXES)


def measure(lines: Iterable[str], objective: float = 0.99, latency_ms: float = 3000) -> Report:
    availability, latency = Sli(), Sli()
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict) or not is_signing_request(entry):
            continue
        server_error = int(entry.get("status", 500)) >= 500
        availability.total += 1
        availability.bad += server_error
        latency.total += 1
        latency.bad += server_error or float(entry.get("duration_ms", 0)) > latency_ms
    return Report(availability, latency, objective, latency_ms)


def render(report: Report) -> str:
    lines = [f"SLO de firma: objetivo {report.objective:.2%}, latencia hasta {report.latency_ms:.0f} ms"]
    for name, sli in (("Disponibilidad", report.availability), ("Latencia", report.latency)):
        lines.append(
            f"  {name:<15} {sli.total - sli.bad}/{sli.total} bien ({sli.good_ratio:.2%})"
            f" · tasa de consumo del presupuesto {sli.burn_rate(report.objective):.1f}x"
        )
    if report.availability.total < MIN_SAMPLE:
        lines.append(f"  Muestra chica ({report.availability.total} pedidos de firma): leer los porcentajes con cuidado.")
    lines.append("  Resultado: " + ("FUERA del objetivo en esta ventana" if report.breached else "dentro del objetivo"))
    return "\n".join(lines)


def _lines(paths: list[str]) -> Iterable[str]:
    if not paths:
        yield from sys.stdin
        return
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as handle:
            yield from handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firmadoc.slo", description="Mide el SLO de firma desde los registros.")
    parser.add_argument("files", nargs="*", help="archivos de registros; sin archivos, la entrada estándar")
    parser.add_argument("--objective", type=float, default=99.0, help="objetivo en porcentaje (por defecto 99)")
    parser.add_argument("--latency-ms", type=float, default=3000, help="umbral de latencia (por defecto 3000)")
    parser.add_argument("--fail-on-breach", action="store_true", help="termina con código 1 si no se cumple")
    args = parser.parse_args(argv)
    if not 0 < args.objective < 100:
        parser.error("--objective debe estar entre 0 y 100")
    report = measure(_lines(args.files), args.objective / 100, args.latency_ms)
    print(render(report))
    return 1 if args.fail_on_breach and report.breached else 0


if __name__ == "__main__":
    raise SystemExit(main())
