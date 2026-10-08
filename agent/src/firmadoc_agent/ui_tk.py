"""Diálogo de confirmación y PIN con tkinter.

tkinter solo puede usarse desde el hilo que creó la ventana. El servidor HTTP corre en otros hilos,
así que sus pedidos llegan por una cola y el hilo principal (`run`) los atiende uno a uno.
"""

import queue
import tkinter as tk
from concurrent.futures import Future
from tkinter import ttk

from .ui import SignPrompt

DEFAULT_TIMEOUT = 120.0
BULLET = "•"


class PinDialog:
    def __init__(self, root: tk.Tk, prompt: SignPrompt, timeout: float, visible: bool = True):
        self.result: str | None = None
        self.timeout = timeout
        top = self.top = tk.Toplevel(root)
        top.title("Firmadoc: confirmar firma")
        top.resizable(False, False)
        top.attributes("-topmost", True)
        top.protocol("WM_DELETE_WINDOW", self.cancel)

        frame = ttk.Frame(top, padding=16)
        frame.grid()
        count = len(prompt.document_names)
        title = "Va a firmar 1 documento" if count == 1 else f"Va a firmar {count} documentos"
        ttk.Label(frame, text=title, font=("Segoe UI", 11, "bold")).grid(sticky="w")

        names = tk.Listbox(frame, height=min(max(count, 1), 8), width=60, activestyle="none")
        for name in prompt.document_names:
            names.insert("end", f"{BULLET} {name}")
        names.grid(sticky="we", pady=(6, 10))

        ttk.Label(frame, text="Certificado:").grid(sticky="w")
        ttk.Label(frame, text=prompt.certificate_subject, wraplength=440).grid(sticky="w")

        if prompt.last_try_warning:
            ttk.Label(
                frame,
                text="ATENCIÓN: queda un único intento antes de que el token se bloquee.",
                foreground="#b00020",
                wraplength=440,
            ).grid(sticky="w", pady=(10, 0))

        ttk.Label(frame, text="PIN del token:").grid(sticky="w", pady=(12, 2))
        self.pin_var = tk.StringVar()
        self.entry = ttk.Entry(frame, textvariable=self.pin_var, show=BULLET, width=30)
        self.entry.grid(sticky="w")

        buttons = ttk.Frame(frame)
        buttons.grid(sticky="e", pady=(16, 0))
        ttk.Button(buttons, text="Cancelar", command=self.cancel).grid(row=0, column=0, padx=6)
        ttk.Button(buttons, text="Firmar", command=self.ok).grid(row=0, column=1)

        top.bind("<Return>", lambda _e: self.ok())
        top.bind("<Escape>", lambda _e: self.cancel())
        if not visible:
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
