import io

from pyhanko.pdf_utils import writer as pw
from pyhanko.pdf_utils.generic import StreamObject


def make_pdf(text: bytes = b"BT 72 720 Td ET") -> bytes:
    w = pw.PdfFileWriter()
    contents = w.add_object(StreamObject(stream_data=text))
    w.insert_page(pw.PageObject(contents=contents, media_box=(0, 0, 595, 842)))
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()
