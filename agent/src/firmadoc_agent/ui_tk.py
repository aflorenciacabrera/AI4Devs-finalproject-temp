"""Diálogo de confirmación y PIN con tkinter.

tkinter solo puede usarse desde el hilo que creó la ventana. El servidor HTTP corre en otros hilos,
así que sus pedidos llegan por una cola y el hilo principal (`run`) los atiende uno a uno.
"""

import queue
import re
import tkinter as tk
from concurrent.futures import Future
from tkinter import ttk

from .ui import SignPrompt

DEFAULT_TIMEOUT = 120.0
BULLET = "•"
_CUIL_RE = re.compile(r"CUIL\s*(\d{11})", re.IGNORECASE)


def subject_parts(subject: str) -> tuple[str, str | None]:
    """Titular (CN) y CUIL de un sujeto como "CN=Juan Perez,serialNumber=CUIL 20111111112"."""
    owner = None
    for part in subject.split(","):
        key, _, value = part.strip().partition("=")
        if key.strip().upper() == "CN" and value.strip():
            owner = value.strip()
            break
    match = _CUIL_RE.search(subject)
    cuil = match.group(1) if match else None
    if cuil:
        cuil = f"{cuil[:2]}-{cuil[2:10]}-{cuil[10:]}"
    return owner or subject, cuil


def center_on_screen(window: tk.Toplevel) -> None:
    """Centra la ventana en la pantalla principal una vez que conoce su tamaño."""
    window.update_idletasks()
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    x = max((window.winfo_screenwidth() - width) // 2, 0)
    y = max((window.winfo_screenheight() - height) // 2 - 40, 0)
    window.geometry(f"+{x}+{y}")


class PinDialog:
    """Ventana mínima: nombre del titular del certificado y PIN; centrada y al frente."""

    def __init__(self, root: tk.Tk, prompt: SignPrompt, timeout: float, visible: bool = True):
        self.result: str | None = None
        self.timeout = timeout
        top = self.top = tk.Toplevel(root)
        top.title("Firmadoc")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.protocol("WM_DELETE_WINDOW", self.cancel)

        frame = ttk.Frame(top, padding=(28, 22, 28, 20))
        frame.grid()
        # Solo el nombre del firmante y el PIN (FIRDOC-51): el CUIL, el sujeto completo y los documentos
        # no se muestran; los nombres de los documentos quedan en el registro de actividad del agente.
        owner, _cuil = subject_parts(prompt.certificate_subject)
        self.owner = owner
        ttk.Label(frame, text="Firmar con el certificado de", foreground="#5b6573").grid(sticky="w")
        ttk.Label(frame, text=owner, font=("Segoe UI", 15, "bold"), wraplength=420).grid(sticky="w", pady=(2, 0))

        if prompt.last_try_warning:
            ttk.Label(
                frame,
                text="ATENCIÓN: queda un único intento antes de que el token se bloquee.",
                foreground="#b00020",
                wraplength=420,
            ).grid(sticky="w", pady=(10, 0))

        ttk.Label(frame, text="PIN del token").grid(sticky="w", pady=(14, 2))
        self.pin_var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.pin_var, show=BULLET, width=24, font=("Segoe UI", 13))
        self.entry.grid(sticky="we")

        buttons = ttk.Frame(frame)
        buttons.grid(sticky="e", pady=(18, 0))
        ttk.Button(buttons, text="Cancelar", command=self.cancel).grid(row=0, column=0, padx=6)
        ttk.Button(buttons, text="Firmar", command=self.ok, default="active").grid(row=0, column=1)

        top.bind("<Return>", lambda _e: self.ok())
        top.bind("<Escape>", lambda _e: self.cancel())
        if visible:
            center_on_screen(top)
            top.lift()
        else:
            top.withdraw()

    def ok(self) -> None:
        pin = self.pin_var.get()
        if not pin:
            return  # sin PIN no se firma; sigue abierto hasta cancelar o agotar el tiempo
        self.result = pin
        self._close()

    def cancel(self) -> None:
        self.result = None
        self._close()

    def _close(self) -> None:
        self.pin_var.set("")  # no dejar el PIN en el widget
        if self.top.winfo_exists():
            self.top.destroy()

    def run(self) -> str | None:
        self.top.after(int(self.timeout * 1000), self.cancel)
        try:
            self.top.grab_set()
            self.entry.focus_force()
        except tk.TclError:
            pass  # ventana no visible (pruebas): no se puede tomar el foco
        self.top.wait_window()
        return self.result


class TkUI:
    def __init__(self, timeout: float = DEFAULT_TIMEOUT, *, visible: bool = True, on_dialog=None):
        self.timeout = timeout
        self.visible = visible
        self.on_dialog = on_dialog  # gancho para pruebas: recibe el diálogo antes de mostrarlo
        self._queue: queue.Queue = queue.Queue()
        self._root: tk.Tk | None = None

    # -- hilo principal --------------------------------------------------------------------

    def run(self, root: tk.Tk | None = None) -> None:
        """Bucle de la interfaz. Bloquea hasta `stop()`; llamarlo desde el hilo principal.

        `root` permite reutilizar una ventana raíz existente (las pruebas comparten una sola:
        crear y destruir varios intérpretes Tcl en un mismo proceso es poco fiable).
        """
        self._root = root or tk.Tk()
        self._root.withdraw()
        self._root.after(100, self._poll)
        self._root.mainloop()

    def _poll(self) -> None:
        assert self._root is not None
        try:
            while True:
                item = self._queue.get_nowait()
                if item is None:
                    self._root.quit()
                    return
                prompt, future = item
                try:
                    dialog = PinDialog(self._root, prompt, self.timeout, self.visible)
                    if self.on_dialog:
                        self.on_dialog(dialog)
                    future.set_result(dialog.run())
                except Exception as e:  # noqa: BLE001 - se informa al hilo que espera
                    future.set_exception(e)
        except queue.Empty:
            pass
        self._root.after(100, self._poll)

    def stop(self) -> None:
        self._queue.put(None)

    # -- hilos del servidor ----------------------------------------------------------------

    def ask_pin(self, prompt: SignPrompt) -> str | None:
        future: Future = Future()
        self._queue.put((prompt, future))
        try:
            return future.result(timeout=self.timeout + 15)
        except TimeoutError:
            return None
