"""Prueba manual del diálogo: muestra la ventana real y dice si se ingresó un PIN (sin mostrarlo).

Uso:  python agent/scripts/try_dialog.py [--ultimo-intento] [--documentos N]
"""

import argparse
import threading

from firmadoc_agent.ui import SignPrompt
from firmadoc_agent.ui_tk import TkUI


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ultimo-intento", action="store_true", help="muestra la advertencia")
    parser.add_argument("--documentos", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()

    ui = TkUI(timeout=args.timeout)
    prompt = SignPrompt(
        document_names=[f"resolucion-{450 + i:04d}.pdf" for i in range(args.documentos)],
        certificate_subject="CN=Juan Perez,2.5.4.5=CUIL 20111111112,C=AR",
        last_try_warning=args.ultimo_intento,
    )

    def worker() -> None:
        pin = ui.ask_pin(prompt)
        print("Cancelado o tiempo agotado." if pin is None else f"PIN ingresado ({len(pin)} caracteres).")
        ui.stop()

    threading.Thread(target=worker, daemon=True).start()
    ui.run()


if __name__ == "__main__":
    main()
