"""Almacenamiento de binarios. Los binarios de versiones son inmutables."""

import hashlib
from pathlib import Path
from typing import Protocol


class StorageError(Exception):
    pass


class DocumentStorage(Protocol):
    def save(self, ref: str, data: bytes) -> None: ...

    def read(self, ref: str) -> bytes: ...

    def delete_prepared(self, ref: str) -> None: ...


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalFileStorage:
    PREPARED_PREFIX = "prepared/"

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _resolve(self, ref: str) -> Path:
        path = (self.root / ref).resolve()
        if self.root not in path.parents:
            raise StorageError(f"referencia fuera del directorio de almacenamiento: {ref}")
        return path

    def save(self, ref: str, data: bytes) -> None:
        path = self._resolve(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "xb") as f:  # "x": nunca sobrescribe
                f.write(data)
        except FileExistsError as e:
            raise StorageError(f"el binario ya existe: {ref}") from e

    def read(self, ref: str) -> bytes:
        path = self._resolve(ref)
        try:
            return path.read_bytes()
        except FileNotFoundError as e:
            raise StorageError(f"binario inexistente: {ref}") from e

    def delete_prepared(self, ref: str) -> None:
        """Solo el estado intermedio de firma es descartable; las versiones nunca se borran."""
        if not ref.startswith(self.PREPARED_PREFIX):
            raise StorageError("solo se pueden borrar referencias 'prepared/'")
        self._resolve(ref).unlink(missing_ok=True)
