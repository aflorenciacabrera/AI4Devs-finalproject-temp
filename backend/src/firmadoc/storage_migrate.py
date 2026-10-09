"""Migra los binarios de las versiones entre almacenes. Uso: `python -m firmadoc.storage_migrate --help`.

Idempotente, verifica cada binario contra el `document_hash` registrado de su versión y NO borra el origen.
Se ejecuta con el servicio detenido.
"""

import argparse
import sys
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import make_engine, make_session_factory
from .models import DocumentVersion
from .storage import DatabaseStorage, LocalFileStorage, StorageError, sha256_hex


@dataclass
class Report:
    copied: int = 0
    skipped: int = 0
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"copiados: {self.copied} · omitidos (ya estaban): {self.skipped} · problemas: {len(self.problems)}"


def _read_or_none(storage, ref: str) -> bytes | None:
    try:
        return storage.read(ref)
    except StorageError:
        return None


def _copy(db: Session, source, target, direction: str) -> Report:
    report = Report()
    for version in db.scalars(select(DocumentVersion).order_by(DocumentVersion.created_at)):
        ref = version.storage_ref
        existing = _read_or_none(target, ref)
        data = _read_or_none(source, ref)
        if existing is not None:
            # Ya está en el destino: una versión creada directamente ahí (sin origen) o ya copiada se omite.
            if data is None or existing == data:
                report.skipped += 1
            else:
                report.problems.append(f"{ref}: ya existe en el destino con contenido distinto (conflicto)")
            continue
        if data is None:
            report.problems.append(f"{ref}: no se pudo leer del origen (binario inexistente o ilegible)")
            continue
        if sha256_hex(data) != version.document_hash:
            report.problems.append(f"{ref}: no coincide con el hash registrado de la versión")
            continue
        target.save(ref, data)
        report.copied += 1
    if direction == "files-to-database":
        db.commit()  # el destino es la base: se confirma al final, todo junto
    return report


def migrate(db: Session, direction: str, storage_dir: str) -> Report:
    files = LocalFileStorage(storage_dir)
    database = DatabaseStorage(db)
    if direction == "files-to-database":
        return _copy(db, files, database, direction)
    return _copy(db, database, files, direction)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="firmadoc.storage_migrate")
    parser.add_argument("direction", choices=["files-to-database", "database-to-files"])
    args = parser.parse_args(argv)
    settings = get_settings()
    engine = make_engine(settings.database_url)
    with make_session_factory(engine)() as db:
        report = migrate(db, args.direction, settings.storage_dir)
    print(report.summary())
    for problem in report.problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
