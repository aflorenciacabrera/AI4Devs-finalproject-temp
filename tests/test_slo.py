"""Medición del SLO de firma desde los registros estructurados (docs/slo/api.md)."""

import json

from firmadoc import slo


def request(route: str, status: int = 200, duration_ms: float = 120.0) -> str:
    return json.dumps({"event": "http_request", "route": route, "status": status, "duration_ms": duration_ms})


COMPLETE = "/api/v1/signature-requests/{request_id}/complete"
WIDGET_PREPARE = "/api/v1/widget/requests/{request_id}/prepare"
BATCH_COMPLETE = "/api/v1/widget/batches/{batch_id}/complete"


def test_solo_cuentan_los_pedidos_de_firma():
    lines = [
        request(COMPLETE),
        request(WIDGET_PREPARE),
        request(BATCH_COMPLETE),
        request("/api/v1/signature-requests/{request_id}"),  # consulta: no es firma
        request("/health"),
        json.dumps({"event": "audit.signed"}),
        "INFO:     Uvicorn running on http://0.0.0.0:8000",  # línea que no es JSON
        "[1, 2, 3]",
    ]
    report = slo.measure(lines)
    assert report.availability.total == 3 and report.availability.bad == 0


def test_un_4xx_no_gasta_presupuesto_y_un_5xx_si():
    report = slo.measure([request(COMPLETE, 409), request(COMPLETE, 422), request(COMPLETE, 503), request(COMPLETE)])
    assert (report.availability.total, report.availability.bad) == (4, 1)


def test_la_latencia_tiene_el_umbral_en_el_borde():
    lines = [request(COMPLETE, duration_ms=3000), request(COMPLETE, duration_ms=3000.1), request(COMPLETE, 500, 10)]
    report = slo.measure(lines, latency_ms=3000)
    assert report.latency.bad == 2  # el que pasa el umbral y el 500, aunque haya sido rápido
    assert slo.measure(lines, latency_ms=2999).latency.bad == 3


def test_tasa_de_consumo_y_resultado():
    lines = [request(COMPLETE)] * 98 + [request(COMPLETE, 500)] * 2  # 2 % de error con un objetivo de 99 %
    report = slo.measure(lines, objective=0.99)
    assert round(report.availability.burn_rate(0.99), 6) == 2.0
    assert report.breached
    assert not slo.measure([request(COMPLETE)] * 199 + [request(COMPLETE, 500)], objective=0.99).breached


def test_sin_pedidos_no_se_inventa_un_incumplimiento():
    report = slo.measure([])
    assert report.availability.good_ratio == 1.0 and not report.breached
    assert "Muestra chica (0 pedidos de firma)" in slo.render(report)


def test_linea_de_comandos(tmp_path, capsys):
    logs = tmp_path / "firmadoc.log"
    logs.write_text("\n".join([request(COMPLETE)] * 9 + [request(COMPLETE, 500)]), encoding="utf-8")
    assert slo.main([str(logs)]) == 0  # informa, no falla
    assert "9/10 bien (90.00%)" in capsys.readouterr().out
    assert slo.main(["--fail-on-breach", str(logs)]) == 1
    assert slo.main(["--fail-on-breach", "--objective", "80", str(logs)]) == 0
