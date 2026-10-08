"""Almacenamiento de binarios. Los binarios de versiones son inmutables."""

import hashlib
from pathlib import Path, PurePosixPath
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import StoredBlob


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


class DatabaseStorage:
    """Binarios en la tabla `stored_blob`, dentro de la transacción de la sesión recibida.

    Guardar no confirma: el binario y la versión que lo referencia se confirman o se revierten juntos
    (sin binarios huérfanos). Los binarios son inmutables también a nivel de base de datos.
    """

    PREPARED_PREFIX = LocalFileStorage.PREPARED_PREFIX

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _check(ref: str) -> None:
        path = PurePosixPath(ref)
        if not ref or "\\" in ref or path.is_absolute() or ".." in path.parts or len(ref) > 500:
            raise StorageError(f"referencia inválida: {ref}")

    def save(self, ref: str, data: bytes) -> None:
        self._check(ref)
        if self.db.get(StoredBlob, ref) is not None:
            raise StorageError(f"el binario ya existe: {ref}")
        self.db.add(StoredBlob(ref=ref, content=data, size=len(data), sha256=sha256_hex(data)))
        try:
            self.db.flush()
        except IntegrityError as e:  # otra transacción lo guardó al mismo tiempo
            raise StorageError(f"el binario ya existe: {ref}") from e

    def read(self, ref: str) -> bytes:
        self._check(ref)
        row = self.db.execute(
            select(StoredBlob.content, StoredBlob.sha256).where(StoredBlob.ref == ref)
        ).first()
        if row is None:
            raise StorageError(f"binario inexistente: {ref}")
        content = bytes(row.content)
        if sha256_hex(content) != row.sha256:
            raise StorageError(f"el binario no coincide con su hash (alterado en la base): {ref}")
        return content

    def delete_prepared(self, ref: str) -> None:
        """Solo el estado intermedio de firma es descartable; las versiones nunca se borran."""
        if not ref.startswith(self.PREPARED_PREFIX):
            raise StorageError("solo se pueden borrar referencias 'prepared/'")
        self._check(ref)
        self.db.execute(delete(StoredBlob).where(StoredBlob.ref == ref))
        self.db.commit()
