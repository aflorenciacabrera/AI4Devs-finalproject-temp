import base64
import hashlib

import pytest

from firmadoc_agent.service import AgentService
from firmadoc_agent.testing import FakeUI, SoftwareBackend
from helpers import soft_token


def hash_item(name: str = "resolucion-0457.pdf", challenge_id: str = "c1", data: bytes = b"x"):
    digest = hashlib.sha256(data + name.encode()).digest()
    return {
        "challenge_id": challenge_id,
        "document_name": name,
        "hash_algorithm": "SHA-256",
        "hash_to_sign": base64.b64encode(digest).decode(),
    }


@pytest.fixture
def token():
    return soft_token()


@pytest.fixture
def backend(token):
    return SoftwareBackend([token], pin="1234", retries=3)


@pytest.fixture
def ui():
    return FakeUI(pin="1234")


@pytest.fixture
def service(backend, ui):
    return AgentService(backend, ui)
