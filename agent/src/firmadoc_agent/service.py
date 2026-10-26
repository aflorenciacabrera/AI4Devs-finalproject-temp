"""Casos de uso del agente: listar certificados y firmar un lote de hashes.

Aquí vive la política de seguridad que no depende de HTTP: se valida el pedido, se confirma con la
persona, se pide el PIN una sola vez y se cierra la sesión pase lo que pase.
"""

import base64
import binascii
import logging
import re
import threading

from . import __version__, errors
from .backend import SHA256_LEN, TokenBackend
from .ui import SignPrompt, UserInterface

log = logging.getLogger("firmadoc_agent")

MAX_ITEMS = 100
MAX_NAME_LEN = 255
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _clean_name(name: str) -> str:
    return _CONTROL.sub(" ", name).strip()


def _short(data: bytes) -> str:
    return data[:4].hex()  # nunca hashes ni firmas completos en el registro


class AgentService:
    def __init__(self, backend: TokenBackend, ui: UserInterface):
        self.backend = backend
        self.ui = ui
        self._signing = threading.Lock()

    # -- GET /certificates -----------------------------------------------------------------

    def list_certificates(self) -> dict:
        certs = self.backend.list_certificates()
        if not certs:
            raise errors.token_not_found()
        return {
            "agent_version": __version__,
            "certificates": [
                {
                    "id": c.id,
                    "token_label": c.token_label,
                    "subject": c.subject,
                    "issuer": c.issuer,
                    "serial_number": c.serial_number,
                    "not_before": c.not_before.isoformat(),
                    "not_after": c.not_after.isoformat(),
                    "certificate_pem": c.pem(),
                }
                for c in certs
            ],
        }

    # -- POST /sign ------------------------------------------------------------------------

    @staticmethod
    def parse_sign_request(body: object) -> tuple[str, list[dict]]:
        if not isinstance(body, dict):
            raise errors.invalid_request("el cuerpo debe ser un objeto JSON")
        certificate_id = body.get("certificate_id")
        items = body.get("items")
        if not isinstance(certificate_id, str) or not certificate_id:
            raise errors.invalid_request("falta 'certificate_id'")
        if not isinstance(items, list) or not items:
            raise errors.invalid_request("'items' debe ser una lista no vacía")
        if len(items) > MAX_ITEMS:
            raise errors.too_many_items(MAX_ITEMS)
        parsed = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise errors.invalid_request(f"items[{i}] debe ser un objeto")
            name = item.get("document_name")
            challenge_id = item.get("challenge_id")
            if not isinstance(name, str) or not _clean_name(name) or len(name) > MAX_NAME_LEN:
                raise errors.invalid_request(f"items[{i}].document_name inválido")
            if not isinstance(challenge_id, str) or not challenge_id:
                raise errors.invalid_request(f"items[{i}].challenge_id inválido")
            if item.get("hash_algorithm") != "SHA-256":
                raise errors.invalid_request(f"items[{i}]: solo se admite hash_algorithm SHA-256")
            try:
                digest = base64.b64decode(item.get("hash_to_sign", ""), validate=True)
            except (binascii.Error, ValueError, TypeError):
                raise errors.invalid_request(f"items[{i}].hash_to_sign no es base64") from None
            if len(digest) != SHA256_LEN:
                raise errors.invalid_request(f"items[{i}].hash_to_sign debe ser de 32 bytes")
            parsed.append(
                {"challenge_id": challenge_id, "name": _clean_name(name), "digest": digest}
            )
        return certificate_id, parsed

    def sign(self, body: object, origin: str = "-") -> dict:
        certificate_id, items = self.parse_sign_request(body)
        if not self._signing.acquire(blocking=False):
            raise errors.busy()
        pin: str | None = None
        try:
            certs = {c.id: c for c in self.backend.list_certificates()}
            cert = certs.get(certificate_id)
            if cert is None:
                raise errors.certificate_not_found()

            prompt = SignPrompt(
                document_names=[i["name"] for i in items],
                certificate_subject=cert.subject,
                last_try_warning=self.backend.final_try(cert.id),
            )
            pin = self.ui.ask_pin(prompt)
            if not pin:
                log.info("firma cancelada origin=%s docs=%s", origin, prompt.document_names)
                raise errors.user_cancelled()

            signatures = self.backend.sign(cert.id, pin, [i["digest"] for i in items])
            log.info(
                "firma ok origin=%s docs=%s cert=%s hashes=%s",
                origin,
                prompt.document_names,
                cert.serial_number,
                [_short(i["digest"]) for i in items],
            )
            return {
                "signatures": [
                    {
                        "challenge_id": item["challenge_id"],
                        "signature_base64": base64.b64encode(sig).decode(),
                    }
                    for item, sig in zip(items, signatures, strict=True)
                ]
            }
        except errors.AgentError as e:
            log.info("firma rechazada origin=%s code=%s", origin, e.code)
            raise
        finally:
            pin = None  # el PIN solo vive mientras dura el login
            self._signing.release()
