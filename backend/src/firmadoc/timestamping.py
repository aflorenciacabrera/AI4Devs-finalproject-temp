"""Sello de tiempo (RFC 3161) de la firma: PAdES B-T."""

from pyhanko.sign.timestamps import HTTPTimeStamper, TimeStamper

from .config import Settings


def make_timestamper(settings: Settings) -> TimeStamper | None:
    """El sellador configurado, o `None` si no hay TSA. Las pruebas reemplazan esta función."""
    if not settings.tsa_url:
        return None
    return HTTPTimeStamper(settings.tsa_url, timeout=settings.tsa_timeout_seconds)
