"""El PDF se descarga con el nombre original del archivo (FIRDOC-53)."""

import uuid
from urllib.parse import unquote

from firmadoc.filenames import clean_filename, content_disposition, download_name, unique_name

DOC_ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


def test_download_name_conserva_acentos_espacios_y_parentesis():
    assert download_name("Resolución 450 (nueva)", DOC_ID) == "Resolución 450 (nueva).pdf"


def test_download_name_no_duplica_la_extension():
    assert download_name("informe.pdf", DOC_ID) == "informe.pdf"
    assert download_name("INFORME.PDF", DOC_ID) == "INFORME.PDF"


def test_download_name_sin_identificador_usa_el_id_del_documento():
    assert download_name(None, DOC_ID) == f"{DOC_ID}.pdf"
    assert download_name("   ", DOC_ID) == f"{DOC_ID}.pdf"


def test_clean_filename_reemplaza_separadores_y_quita_control_y_comillas():
    assert clean_filename('..\\dir/exp/"1"\r\nX') == ".._dir_exp_1X"
    assert clean_filename("exp-1/doc-1") == "exp-1_doc-1"
    assert clean_filename("a" * 300) == "a" * 200
    assert clean_filename("nombre.") == "nombre"


def test_unique_name_numera_los_repetidos_antes_de_la_extension():
    used: set[str] = set()
    assert unique_name("acta.pdf", used) == "acta.pdf"
    assert unique_name("acta.pdf", used) == "acta-2.pdf"
    assert unique_name("acta.pdf", used) == "acta-3.pdf"
    assert unique_name("sin-extension", used) == "sin-extension"
    assert unique_name("sin-extension", used) == "sin-extension-2"


def test_content_disposition_lleva_el_nombre_exacto_en_utf8_y_un_fallback_ascii():
    header = content_disposition("Resolución 450 – final.pdf")  # con acento y guion largo
    assert header.startswith('attachment; filename="Resolucion 450 _ final.pdf"; filename*=UTF-8\'\'')
    assert unquote(header.split("filename*=UTF-8''")[1]) == "Resolución 450 – final.pdf"
    header.encode("ascii")  # la cabecera es transmisible por cualquier cliente


def test_content_disposition_sanea_comillas_y_saltos_de_linea():
    header = content_disposition('exp/"1"\r\nX: y.pdf')
    assert "\r" not in header and "\n" not in header and '"1"' not in header
    assert 'filename="exp_1X: y.pdf"' in header


def test_content_disposition_sin_nombre():
    assert content_disposition("") == "attachment; filename=\"documento.pdf\"; filename*=UTF-8''documento.pdf"
