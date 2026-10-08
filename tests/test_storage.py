import pytest

from firmadoc.storage import LocalFileStorage, StorageError, sha256_hex


def test_guardar_y_leer(tmp_path):
    s = LocalFileStorage(tmp_path)
    s.save("documents/a/v1.pdf", b"contenido")
    data = s.read("documents/a/v1.pdf")
    assert data == b"contenido"
    assert sha256_hex(data) == sha256_hex(b"contenido")


def test_no_sobrescribe(tmp_path):
    s = LocalFileStorage(tmp_path)
    s.save("documents/a/v1.pdf", b"original")
    with pytest.raises(StorageError):
        s.save("documents/a/v1.pdf", b"otro")
    assert s.read("documents/a/v1.pdf") == b"original"


@pytest.mark.parametrize("ref", ["../fuera.pdf", "documents/../../fuera.pdf", "/etc/passwd"])
def test_ruta_maliciosa(tmp_path, ref):
    s = LocalFileStorage(tmp_path / "root")
    with pytest.raises(StorageError):
        s.save(ref, b"x")
    with pytest.raises(StorageError):
        s.read(ref)


def test_solo_se_borra_estado_intermedio(tmp_path):
    s = LocalFileStorage(tmp_path)
    s.save("documents/a/v1.pdf", b"x")
    with pytest.raises(StorageError):
        s.delete_prepared("documents/a/v1.pdf")
    s.save("prepared/c/doc.pdf", b"x")
    s.delete_prepared("prepared/c/doc.pdf")
