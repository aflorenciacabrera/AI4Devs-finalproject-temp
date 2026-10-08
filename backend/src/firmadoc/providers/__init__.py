from functools import lru_cache

from ..certificate_validation import CertificateChecker, load_crls
from ..config import Settings
from ..errors import Unprocessable
from ..models import Provider
from ..trust import load_trust_store
from .base import SignatureProvider
from .firmar import RemoteProvider
from .local import LocalPAdESProvider
from .token import TokenAgentProvider

ENABLED = {Provider.LOCAL, Provider.TOKEN}


@lru_cache
def _local(cert_dir: str) -> LocalPAdESProvider:
    return LocalPAdESProvider(cert_dir)


def _token(settings: Settings) -> TokenAgentProvider:
    trust = load_trust_store(settings.trust_dir)
    checker = CertificateChecker(
        trust,
        settings.revocation_mode,
        allow_fetching=settings.revocation_fetch,
        crls=load_crls(settings.crl_dir),
    )
    return TokenAgentProvider(checker, trust)


def get_provider(provider: Provider, settings: Settings) -> SignatureProvider:
    if provider == Provider.FIRMAR and settings.firmar_base_url:
        return RemoteProvider()  # type: ignore[return-value]  # familia distinta: recibe el PDF completo
    if provider not in ENABLED:
        raise Unprocessable(f"el proveedor '{provider.value}' todavía no está habilitado")
    if provider == Provider.TOKEN:
        return _token(settings)
    return _local(settings.local_cert_dir)
