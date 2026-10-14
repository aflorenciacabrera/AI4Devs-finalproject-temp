/**
 * `<firmadoc-widget signing-url="...">`: envoltorio del iframe del widget para la página anfitriona.
 *
 * Es un envoltorio, no un componente en página: el aislamiento del iframe se mantiene (sin CORS ni
 * estilos filtrados) y hay una única implementación del widget. Reemite los mensajes del widget como
 * eventos DOM, solo si vienen de su propio iframe y del origen de la `signing-url`.
 */

const EVENTS: Record<string, string> = {
  "firmadoc:ready": "firmadoc-ready",
  "firmadoc:signed": "firmadoc-signed",
  "firmadoc:batch-completed": "firmadoc-batch-completed",
  "firmadoc:failed": "firmadoc-failed",
  "firmadoc:cancelled": "firmadoc-cancelled",
  "firmadoc:closed": "firmadoc-closed",
};

const CSS = `
:host { display: block; width: 480px; max-width: 100%; height: 760px; max-height: min(760px, 80vh); }
iframe { display: block; width: 100%; height: 100%; border: 0; }
`;

/** Alto informado por el widget, en píxeles. Fuera de rango no se aplica. */
function frameHeightPx(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value < 1) return null;
  return Math.min(4000, Math.ceil(value));
}

/**
 * El iframe necesita delegar el permiso de acceso a la red local para hablar con el agente en
 * 127.0.0.1 (Chrome 142+). Los nombres de la política cambiaron entre versiones del navegador y los
 * desconocidos se ignoran: se declaran todos.
 */
const ALLOW = "local-network-access; local-network; loopback-network";
const SANDBOX = "allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox";

export class FirmadocWidgetElement extends HTMLElement {
  static observedAttributes = ["signing-url"];

  private frame: HTMLIFrameElement | null = null;
  private expectedOrigin: string | null = null;
  private readonly onMessage = (event: MessageEvent) => this.handleMessage(event);

  connectedCallback(): void {
    if (!this.shadowRoot) {
      const root = this.attachShadow({ mode: "open" });
      try {
        const sheet = new CSSStyleSheet();
        sheet.replaceSync(CSS);
        root.adoptedStyleSheets = [sheet]; // por CSSOM: no lo bloquea la CSP del anfitrión
      } catch {
        // navegadores sin hojas de estilo construibles: el tamaño se define con CSS del anfitrión
      }
    }
    window.addEventListener("message", this.onMessage);
    this.render();
  }

  disconnectedCallback(): void {
    window.removeEventListener("message", this.onMessage);
  }

  attributeChangedCallback(): void {
    if (this.isConnected) this.render();
  }

  private render(): void {
    const root = this.shadowRoot;
    if (!root) return;
    const raw = this.getAttribute("signing-url");
    let url: URL | null;
    try {
      url = raw ? new URL(raw, window.location.href) : null;
    } catch {
      url = null;
    }
    if (!url || (url.protocol !== "https:" && url.protocol !== "http:")) {
      this.frame?.remove();
      this.frame = null;
      this.expectedOrigin = null;
      if (raw) this.emit("firmadoc-failed", { source: "firmadoc", type: "firmadoc:failed", code: "invalid_url" });
      return;
    }
    this.expectedOrigin = url.origin;
    if (!this.frame) {
      const frame = document.createElement("iframe");
      frame.title = "Firma de documento (Firmadoc)";
      frame.setAttribute("allow", ALLOW);
      frame.setAttribute("sandbox", SANDBOX);
      frame.referrerPolicy = "no-referrer";
      root.appendChild(frame);
      this.frame = frame;
    }
    this.frame.src = url.href;
  }

  private handleMessage(event: MessageEvent): void {
    const frame = this.frame;
    if (!frame || event.source !== frame.contentWindow) return; // solo desde su propio iframe
    if (event.origin !== this.expectedOrigin) return; // y desde el origen de la signing-url
    const data: unknown = event.data;
    if (typeof data !== "object" || data === null) return;
    const message = data as { source?: unknown; type?: unknown };
    if (message.source !== "firmadoc" || typeof message.type !== "string") return;
    if (message.type === "firmadoc:resize") {
      const height = frameHeightPx((data as { height?: unknown }).height);
      if (height !== null) {
        this.style.height = `${height}px`;
        this.emit("firmadoc-resize", data);
      }
      return;
    }
    const name = EVENTS[message.type];
    if (name) this.emit(name, data);
  }

  private emit(name: string, detail: unknown): void {
    this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));
  }
}

if (typeof customElements !== "undefined" && !customElements.get("firmadoc-widget")) {
  customElements.define("firmadoc-widget", FirmadocWidgetElement);
}
