"""Registros estructurados: identificador por pedido, un registro por pedido y nada sensible en ellos."""

import io
import json
import logging

import pytest

from firmadoc import observability
from firmadoc.observability import (
    JsonFormatter,
    TextFormatter,
    accept_request_id,
    configure_logging,
    log_event,
)

from .test_flow import SIGNER, create, sign_fully


@pytest.fixture
def logs():
    """Captura lo que escribe el logger `firmadoc` con el formato JSON real; devuelve los registros parseados."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger(observability.LOGGER)
    previous = (logger.level, logger.propagate)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield lambda: [json.loads(line) for line in stream.getvalue().splitlines()]
    logger.removeHandler(handler)
    logger.setLevel(previous[0])
    logger.propagate = previous[1]


def test_cada_respuesta_lleva_un_identificador_de_pedido(client):
    a = client.get("/health").headers["X-Request-ID"]
    b = client.get("/health").headers["X-Request-ID"]
    assert len(a) == 32 and a != b


def test_se_respeta_el_identificador_del_integrador_si_tiene_forma_segura(client):
    r = client.get("/health", headers={"X-Request-ID": "gestor-2026.11_abc-001"})
    assert r.headers["X-Request-ID"] == "gestor-2026.11_abc-001"


@pytest.mark.parametrize("raro", ["corto", "con espacios adentro", 'comillas"y{llaves}', "x" * 65, "salto\\nde-linea"])
def test_un_identificador_ajeno_con_forma_rara_se_reemplaza(raro):
    nuevo = accept_request_id(raro)
    assert nuevo != raro and len(nuevo) == 32


def test_un_registro_por_pedido_con_ruta_declarada_estado_y_duracion(client, logs):
    created = create(client, callback_url=None).json()
    rid = client.get(f"/api/v1/signature-requests/{created['id']}?basura=1").headers["X-Request-ID"]
    http = [e for e in logs() if e["event"] == "http_request"]
    last = http[-1]
    assert last["request_id"] == rid
    assert last["method"] == "GET"
    assert last["route"] == "/api/v1/signature-requests/{request_id}"  # la ruta declarada, no una por documento
    assert last["status"] == 200
    assert last["duration_ms"] >= 0
    assert "basura" not in json.dumps(last)  # la cadena de consulta no se registra


def test_un_error_del_dominio_tambien_queda_registrado_con_su_estado(client, logs):
    client.get("/api/v1/signature-requests/00000000-0000-0000-0000-000000000000")
    assert [e["status"] for e in logs() if e["event"] == "http_request"][-1] == 404


def test_health_solo_se_registra_en_debug(client, logs):
    client.get("/health")
    entry = [e for e in logs() if e["event"] == "http_request"][-1]
    assert entry["level"] == "debug" and entry["route"] == "/health"


def test_la_firma_deja_eventos_unidos_por_el_identificador_del_pedido(client, logs):
    signed = sign_fully(client)
    entries = logs()
    events = [e["event"] for e in entries if e["event"].startswith("audit.")]
    assert events[0] == "audit.created" and "audit.prepared" in events and events[-1] == "audit.signed"
    assert all(e["signature_request_id"] == signed["id"] for e in entries if e["event"].startswith("audit."))
    # el evento `signed` comparte identificador con el pedido HTTP de `complete`
    signed_event = next(e for e in entries if e["event"] == "audit.signed")
    complete = next(e for e in entries if e["event"] == "http_request" and e["route"].endswith("/complete"))
    assert signed_event["request_id"] == complete["request_id"]
    assert signed_event["signature_level"] == "B-B"
    assert next(e for e in entries if e["event"] == "audit.created")["provider"] == "local"


def test_los_registros_no_llevan_datos_personales_ni_material_sensible(client, logs):
    sign_fully(client)
    text = json.dumps(logs(), ensure_ascii=False)
    for forbidden in (SIGNER["full_name"], SIGNER["identifier"], SIGNER["email"], "JVBERi0", "X-API-Key", "BEGIN CERT"):
        assert forbidden not in text
    assert client.headers["X-API-Key"] not in text


def test_un_campo_sensible_pasado_por_error_se_omite(logs):
    log_event("prueba", pin="1234", api_key="clave", signer_email="a@b.c", cuil="20123456789", provider="token")
    entry = logs()[-1]
    assert entry["provider"] == "token"
    assert {entry[k] for k in ("pin", "api_key", "signer_email", "cuil")} == {observability.OMITTED}
    assert "1234" not in json.dumps(entry) and "20123456789" not in json.dumps(entry)


def test_formato_de_texto_para_desarrollo():
    record = logging.LogRecord("firmadoc.events", logging.INFO, __file__, 1, "audit.signed", None, None)
    record.fields = {"provider": "local", "pin": "1234"}
    line = TextFormatter().format(record)
    assert "audit.signed" in line and "provider=local" in line and "1234" not in line


def test_configurar_dos_veces_no_duplica_los_registros(capsys):
    logger = logging.getLogger(observability.LOGGER)
    previous = (logger.level, logger.propagate, list(logger.handlers))
    try:
        configure_logging("json", "INFO")
        configure_logging("json", "INFO")
        log_event("una_sola_vez")
        assert capsys.readouterr().out.count("una_sola_vez") == 1
    finally:
        logger.handlers[:] = previous[2]
        logger.setLevel(previous[0])
        logger.propagate = previous[1]


def test_formato_y_nivel_invalidos_se_rechazan_al_configurar(settings):
    from firmadoc.config import Settings

    with pytest.raises(ValueError):
        Settings(log_format="xml")
    with pytest.raises(ValueError):
        Settings(log_level="CHISME")
    assert Settings(log_level="debug").log_level == "DEBUG"
