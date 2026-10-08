from functools import lru_cache

from ..errors import Unprocessable
from ..models import Provider
from .base import SignatureProvider
from .local import LocalPAdESProvider

ENABLED = {Provider.LOCAL}


@lru_cache
def _local(cert_dir: str) -> LocalPAdESProvider:
    return LocalPAdESProvider(cert_dir)


def get_provider(provider: Provider, local_cert_dir: str) -> SignatureProvider:
    if provider not in ENABLED:
        raise Unprocessable(f"el proveedor '{provider.value}' todavía no está habilitado")
    return _local(local_cert_dir)
