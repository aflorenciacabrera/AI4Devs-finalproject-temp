"""Diálogo tkinter. Se omite si no hay pantalla. Las ventanas se crean ocultas."""

import threading

import pytest

tk = pytest.importorskip("tkinter")

from firmadoc_agent.ui import SignPrompt
from firmadoc_agent.ui_tk import PinDialog, TkUI

PROMPT = SignPrompt(["a.pdf", "b.pdf"], "CN=Juan Perez", last_try_warning=False)


@pytest.fixture(scope="module")
def root():
    """Una única raíz Tk para todo el módulo (varios intérpretes por proceso no son fiables)."""
    try:
        r = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"no hay pantalla disponible: {e}")
    r.withdraw()
    yield r
    r.destroy()


def labels(dialog):
    out = []
    stack = [dialog.top]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        if w.winfo_class() in {"TLabel", "Label"}:
            out.append(str(w.cget("text")))
        if w.winfo_class() == "Listbox":
            out.extend(w.get(0, "end"))
    return "\n".join(out)


def test_muestra_nombres_y_certificado(root):
    d = PinDialog(root, PROMPT, timeout=5, visible=False)
    text = labels(d)
    assert "a.pdf" in text and "b.pdf" in text
    assert "Va a firmar 2 documentos" in text
    assert "CN=Juan Perez" in text
    assert "último intento" not in text.lower()
    d.cancel()


def test_advertencia_de_ultimo_intento(root):
    prompt = SignPrompt(["a.pdf"], "CN=X", last_try_warning=True)
    d = PinDialog(root, prompt, timeout=5, visible=False)
    assert "único intento" in labels(d)
    d.cancel()


def test_el_pin_se_enmascara(root):
    d = PinDialog(root, PROMPT, timeout=5, visible=False)
    assert d.entry.cget("show") != ""
    d.cancel()


def test_aceptar_devuelve_el_pin_y_lo_borra_del_widget(root):
    d = PinDialog(root, PROMPT, timeout=5, visible=False)
    d.pin_var.set("1234")
    root.after(30, d.ok)
    assert d.run() == "1234"
    assert d.pin_var.get() == ""


def test_cancelar_devuelve_none(root):
    d = PinDialog(root, PROMPT, timeout=5, visible=False)
    d.pin_var.set("1234")
    root.after(30, d.cancel)
    assert d.run() is None
    assert d.pin_var.get() == ""


def test_sin_pin_no_se_puede_aceptar(root):
    d = PinDialog(root, PROMPT, timeout=5, visible=False)
    root.after(30, d.ok)  # PIN vacío: se ignora
    root.after(80, d.cancel)
    assert d.run() is None


def test_tiempo_agotado_cancela(root):
    d = PinDialog(root, PROMPT, timeout=0.1, visible=False)
    assert d.run() is None


def test_tkui_atiende_pedidos_de_otros_hilos(root):
    def answer(dialog):
        def fill():
            dialog.pin_var.set("9876")
            dialog.ok()

        dialog.top.after(20, fill)

    ui = TkUI(timeout=5, visible=False, on_dialog=answer)
    result = {}

    def worker():
        result["pin"] = ui.ask_pin(PROMPT)
        ui.stop()

    threading.Thread(target=worker, daemon=True).start()
    ui.run(root)  # hilo principal: termina cuando el worker llama a stop()
    assert result["pin"] == "9876"
