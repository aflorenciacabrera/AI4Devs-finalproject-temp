"""Carga de un PDF desde el panel: sistema interno, endpoint, auditoría y embebido del widget."""

import base64
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from firmadoc import integrators
from firmadoc.main import app
from firmadoc.models import (
    AdminEvent,
    Document,
    DocumentVersion,
    IntegratingSystem,
    SignatureRequest,
    Signer,
    VersionOrigin,
)
from firmadoc.services.panel_upload import PANEL_SYSTEM_NAME

from .pdfs import make_pdf
from .test_flow import create

TOKEN = "t0ken-de-administracion-" + "x" * 20
URL = "/api/v1/admin/signing-uploads"


@pytest.fixture
def admin(client, settings):
    settings.admin_token = TOKEN
    return {"Authorization": f"Bearer {TOKEN}"}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def upload(client, admin, data: bytes | None = None, **extra):
    body = {"filename": "Resolucion_0142-2026.pdf", "document_base64": b64(data or make_pdf()), **extra}
    return client.post(URL, headers=admin, json=body)


def count(session, model) -> int:
    session.expire_all()
    return session.scalar(select(func.count()).select_from(model))


def signer_name(session, request_id: str) -> str:
    session.expire_all()
    return session.get(Signer, session.get(SignatureRequest, uuid.UUID(request_id)).signer_id).full_name


def panel_systems(session) -> list[IntegratingSystem]:
    session.expire_all()
    return list(session.scalars(select(IntegratingSystem).where(IntegratingSystem.name == PANEL_SYSTEM_NAME)))


# --- carga --------------------------------------------------------------------------------------------


def test_carga_valida(client, admin, session):
    pdf = make_pdf()
    r = upload(client, admin, pdf)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "Resolucion_0142-2026.pdf"
    assert body["page_count"] == 1
    assert body["size_bytes"] == len(pdf)
    assert body["signing_url"].startswith(f"http://test/sign/{body['request_id']}#t=")

    session.expire_all()
    version = session.scalar(select(DocumentVersion).where(DocumentVersion.document_id == uuid.UUID(body["document_id"])))
    assert version.version_number == 1
    assert version.origin == VersionOrigin.UPLOADED
    assert version.document_hash == body["document_hash"]
    request = session.get(SignatureRequest, uuid.UUID(body["request_id"]))
    assert request.status.value == "pending"
    assert request.integrating_system_id == panel_systems(session)[0].id


def test_firmante_por_defecto_y_firmante_propio(client, admin, session):
    r = upload(client, admin)
    session.expire_all()
    assert signer_name(session, r.json()["request_id"]) == "Operador del panel"

    signer = {"full_name": "Ana Pérez", "identifier": "20123456786", "email": "ana@example.org"}
    r = upload(client, admin, signer=signer)
    assert r.status_code == 201
    session.expire_all()
    assert signer_name(session, r.json()["request_id"]) == "Ana Pérez"


def test_metodos_habilitados(client, admin, session):
    r = upload(client, admin)
    session.expire_all()
    request = session.get(SignatureRequest, uuid.UUID(r.json()["request_id"]))
    assert request.provider.value == "token"  # el primero disponible; firmar no está configurado
    assert request.allowed_providers == "token,local"


def test_en_modo_real_no_se_ofrece_el_local(client, admin, session, settings):
    settings.real_mode = True
    r = upload(client, admin)
    assert r.status_code == 201
    session.expire_all()
    assert session.get(SignatureRequest, uuid.UUID(r.json()["request_id"])).allowed_providers == "token"


@pytest.mark.parametrize("payload", ["no-es-base64!!", base64.b64encode(b"texto plano").decode()])
def test_archivo_invalido(client, admin, session, payload):
    before = (count(session, Document), count(session, SignatureRequest))
    r = client.post(URL, headers=admin, json={"filename": "x.pdf", "document_base64": payload})
    assert r.status_code == 422
    assert (count(session, Document), count(session, SignatureRequest)) == before
    assert panel_systems(session) == []


def test_excede_el_tamano(client, admin, session, settings):
    settings.max_document_bytes = 100
    before = (count(session, Document), count(session, DocumentVersion))
    assert upload(client, admin).status_code == 422
    assert (count(session, Document), count(session, DocumentVersion)) == before


def test_sin_credenciales(client, admin, settings):
    assert client.post(URL, json={"filename": "x.pdf", "document_base64": b64(make_pdf())}).status_code == 401
    assert client.post(URL, headers={"Authorization": "Bearer otro"}, json={}).status_code == 401
    settings.admin_token = None
    assert client.post(URL, headers=admin, json={}).status_code == 404


def test_el_nombre_de_archivo_se_sanea(client, admin):
    name = r"C:\temp\..\sub/<img src=x onerror=alert(1)>.pdf"
    r = client.post(URL, headers=admin, json={"filename": name, "document_base64": b64(make_pdf())})
    assert r.json()["filename"] == "<img src=x onerror=alert(1)>.pdf"  # sin ruta; el panel lo muestra como texto


# --- sistema interno ----------------------------------------------------------------------------------


def test_sistema_interno_se_crea_una_vez(client, admin, session):
    assert panel_systems(session) == []
    upload(client, admin)
    upload(client, admin)
    systems = panel_systems(session)
    assert len(systems) == 1
    assert systems[0].allowed_origins == "http://test"


def test_ninguna_api_key_autentica_contra_el_sistema_interno(client, admin, session):
    upload(client, admin)
    system = panel_systems(session)[0]
    for key in ("fdk_panel", system.api_key_hash, ""):
        r = client.get(f"/api/v1/documents/{uuid_zero()}", headers={"X-API-Key": key})
        assert r.status_code == 401


def uuid_zero() -> str:
    return "00000000-0000-0000-0000-000000000000"


def test_el_alta_de_integradores_rechaza_el_nombre_reservado(session):
    with pytest.raises(ValueError, match="reservado"):
        integrators.create(session, PANEL_SYSTEM_NAME, "https://a.example.org")
    with pytest.raises(ValueError, match="reservado"):
        integrators.create(session, "  " + PANEL_SYSTEM_NAME, "")


# --- auditoría ----------------------------------------------------------------------------------------


def test_auditoria_sin_contenido(client, admin, session):
    pdf = make_pdf(b"BT secreto-del-documento ET")
    body = upload(client, admin, pdf).json()
    session.expire_all()
    event = session.scalar(select(AdminEvent).where(AdminEvent.action == "panel_upload"))
    assert event.detail["document_id"] == body["document_id"]
    assert event.detail["filename"] == "Resolucion_0142-2026.pdf"
    assert event.detail["document_hash"] == body["document_hash"]
    assert b64(pdf) not in str(event.detail) and "secreto" not in str(event.detail)

    listed = client.get("/api/v1/admin/events", headers=admin).json()
    assert any(e["action"] == "panel_upload" for e in listed["items"])


# --- embebido del widget ------------------------------------------------------------------------------


def frame_ancestors(response) -> str:
    csp = response.headers["content-security-policy"]
    return next(p for p in csp.split("; ") if p.startswith("frame-ancestors"))


def test_el_panel_puede_embeber_su_solicitud(client, admin, settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>")
    settings.widget_dist = str(dist)
    body = upload(client, admin).json()
    r = client.get(f"/sign/{body['request_id']}")
    assert r.status_code == 200
    assert frame_ancestors(r) == "frame-ancestors http://test"


def test_el_panel_no_puede_embeber_solicitudes_de_otros_integradores(client, settings, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>")
    settings.widget_dist = str(dist)
    request_id = create(client).json()["id"]  # integrador demo
    r = client.get(f"/sign/{request_id}")
    assert "http://test" not in frame_ancestors(r)


def test_firma_completa_de_una_solicitud_del_panel(client, admin, session):
    body = upload(client, admin).json()
    rid = body["request_id"]
    token = body["signing_url"].partition("#t=")[2]
    h = {"Authorization": f"Bearer {token}", "X-Session-Ref": "sesion-1"}
    anon = TestClient(app)
    base = f"/api/v1/widget/requests/{rid}"
    assert anon.post(f"{base}/provider", json={"provider": "local"}, headers=h).status_code == 200
    assert anon.post(f"{base}/prepare", json={}, headers=h).status_code == 200
    done = anon.post(f"{base}/complete", json={"signatures": []}, headers=h)
    assert done.status_code == 200, done.text
    assert done.json()["document"]["version_number"] == 2
    session.expire_all()
    versions = list(
        session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == uuid.UUID(body["document_id"]))
            .order_by(DocumentVersion.version_number)
        )
    )
    assert [v.version_number for v in versions] == [1, 2]
    assert session.get(Document, uuid.UUID(body["document_id"])).current_version_id == versions[1].id
