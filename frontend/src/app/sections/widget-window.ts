import { Injectable } from '@angular/core';
import { SignResult, parseWidgetMessage } from '../core/widget-messages';

/** Lo que el panel necesita de la ventana abierta (lo que devuelve `window.open`). */
export interface PopupLike {
  closed: boolean;
  location: { href: string };
  document?: { write(html: string): void; close(): void };
  close(): void;
  focus(): void;
}

export interface WidgetWindowCallbacks {
  /** Cada resultado que informa el widget (firmado, lote, fallo, cancelación). */
  onResult: (result: SignResult) => void;
  /** La ventana se cerró (por «Cerrar» del widget o por la persona). Se llama una sola vez. */
  onClosed: () => void;
}

export interface WidgetWindowHandle {
  /** Carga la `signing_url` en la ventana reservada y empieza a escuchar sus mensajes. */
  open(signingUrl: string, callbacks: WidgetWindowCallbacks): void;
  /** Trae la ventana al frente. */
  focus(): void;
  /** Cierra la ventana y deja de escuchar (no llama a `onClosed`). */
  close(): void;
}

const NAME = 'firmadoc-firma';
const WIDTH = 560;
const HEIGHT = 860;
const POLL_MS = 300;

const WAITING_HTML =
  '<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Firmadoc</title>' +
  '<style>body{font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0;color:#374151}</style>' +
  '</head><body><p>Preparando el documento…</p></body></html>';

/**
 * Widget de firma en una **ventana propia** (`window.open`): Firmadoc es la página principal de esa ventana, así
 * que el permiso de acceso a la red local se le pide a su propio origen (sin delegarlo por `allow`) y no queda un
 * módulo dentro de un diálogo. El widget avisa por `window.opener`; acá se aceptan solo los mensajes que vienen de
 * esa ventana y del origen de la `signing_url`.
 *
 * `reserve()` debe llamarse en el gesto del usuario (clic): si no, el navegador bloquea la ventana. Devuelve `null`
 * cuando la bloqueó igual; entonces el panel usa el diálogo como respaldo.
 */
@Injectable({ providedIn: 'root' })
export class WidgetWindow {
  reserve(): WidgetWindowHandle | null {
    const left = Math.max(0, Math.round(window.screenX + (window.outerWidth - WIDTH) / 2));
    const top = Math.max(0, Math.round(window.screenY + (window.outerHeight - HEIGHT) / 2));
    const features = `popup=yes,width=${WIDTH},height=${HEIGHT},left=${left},top=${top},resizable=yes,scrollbars=yes`;
    const popup = window.open('', NAME, features) as PopupLike | null;
    if (!popup) return null;
    try {
      popup.document?.write(WAITING_HTML);
      popup.document?.close();
    } catch {
      // la ventana reservada no es nuestra (reutilizada con otro origen): igual se navega enseguida
    }
    return new Handle(popup);
  }
}

class Handle implements WidgetWindowHandle {
  private origin = '';
  private callbacks: WidgetWindowCallbacks | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private finished = false;
  private readonly onMessage = (event: MessageEvent) => {
    if (this.finished || event.source !== this.popup || event.origin !== this.origin) return;
    const outcome = parseWidgetMessage(event.data);
    if (!outcome) return;
    if (outcome.kind === 'closed') this.finish(true);
    else this.callbacks?.onResult(outcome.result);
  };

  constructor(private readonly popup: PopupLike) {}

  open(signingUrl: string, callbacks: WidgetWindowCallbacks): void {
    this.origin = new URL(signingUrl, location.href).origin;
    this.callbacks = callbacks;
    window.addEventListener('message', this.onMessage);
    this.popup.location.href = signingUrl;
    this.timer = setInterval(() => {
      if (this.popup.closed) this.finish(true);
    }, POLL_MS);
  }

  focus(): void {
    if (!this.popup.closed) this.popup.focus();
  }

  close(): void {
    this.finish(false);
  }

  private finish(notify: boolean): void {
    if (this.finished) return;
    this.finished = true;
    window.removeEventListener('message', this.onMessage);
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    if (!this.popup.closed) this.popup.close();
    if (notify) this.callbacks?.onClosed();
  }
}
