"""Nombres de archivo de los PDF: el que se cargó es el que se descarga (FIRDOC-53).

El panel registra el nombre original (sin `.pdf`) como `external_document_id`; los integradores mandan el
identificador que quieran. De ahí sale el nombre que ve el firmante en el widget, el que queda en el registro
del agente y el del archivo descargado. Solo se quitan separadores de ruta, caracteres de control y comillas.
"""

import re
import unicodedata
import uuid
from urllib.parse import quote

_SEPARATORS = re.compile(r"[\\/]")
_FORBIDDEN = re.compile(r'[\x00-\x1f\x7f"]')
_PDF = ".pdf"


def clean_filename(name: str) -> str:
    """Un nombre de archivo seguro para cabeceras y ZIP, sin alterar acentos, espacios ni paréntesis.

    Los separadores de ruta pasan a `_` (un identificador como `exp-1/doc-1` sigue legible); las comillas
    y los caracteres de control se quitan.
    """
    name = unicodedata.normalize("NFC", name)
    name = _FORBIDDEN.sub("", _SEPARATORS.sub("_", name)).strip().rstrip(".")
    return name[:200]


def download_name(external_document_id: str | None, document_id: uuid.UUID | str) -> str:
    """Nombre con el que se descarga un documento: el original con `.pdf` (una sola vez)."""
    base = clean_filename(external_document_id or "") or str(document_id)
    return base if base.lower().endswith(_PDF) else base + _PDF


def unique_name(name: str, used: set[str]) -> str:
    """`name`, o `name-2`, `name-3`… (antes de la extensión) si ya se usó. Registra el elegido en `used`."""
    stem, ext = (name[: -len(_PDF)], _PDF) if name.lower().endswith(_PDF) else (name, "")
    candidate, n = name, 2
    while candidate in used:
        candidate = f"{stem}-{n}{ext}"
        n += 1
    used.add(candidate)
    return candidate


def ascii_fallback(filename: str) -> str:
    """El nombre sin acentos (`Resolución` → `Resolucion`); lo que no se pueda transliterar pasa a `_`."""
    decomposed = unicodedata.normalize("NFKD", filename)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return "".join(c if c.isascii() and c.isprintable() else "_" for c in stripped)


def content_disposition(filename: str) -> str:
    """`attachment` con `filename` (solo ASCII: las cabeceras HTTP no admiten otra cosa de forma fiable)
    y `filename*` (el nombre exacto en UTF-8, RFC 6266), que los clientes de Firmadoc leen primero."""
    filename = clean_filename(filename) or "documento.pdf"
    return f"attachment; filename=\"{ascii_fallback(filename)}\"; filename*=UTF-8''{quote(filename, safe='')}"


def attachment_headers(filename: str) -> dict[str, str]:
    return {"Content-Disposition": content_disposition(filename), "Cache-Control": "no-store"}
