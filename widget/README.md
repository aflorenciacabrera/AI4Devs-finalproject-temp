# Widget de firma de Firmadoc

Interfaz de firma que un sistema integrador **embebe** en su propia pantalla. Coordina al servidor de Firmadoc con el agente local: lista los certificados del token, valida el certificado **antes** de pedir el PIN, hace que el agente firme el hash y registra la nueva versión del documento.

- Stack: React + TypeScript (Vite), español rioplatense, accesible por teclado y lectores de pantalla.
- Proveedores: `token` (firma digital con el token, vía el agente), `local` (firma electrónica de demostración) y `firmar` (firma remota: abre el servicio en otra pestaña y espera su resultado).
- **El widget nunca ve el PIN**: se ingresa en la ventana de Firmadoc Agent, en la PC de la persona.

## Cómo se integra

1. **El backend del integrador** (nunca el navegador) crea la solicitud con su API key:

   ```http
   POST /api/v1/signature-requests
   X-API-Key: <api key del integrador>
   ```

   y recibe una `signing_url` con la forma `https://firmadoc.example.org/sign/{id}#t={token}`.
2. Entrega esa `signing_url` a su pantalla (por ejemplo en la respuesta de su propia API).
3. La pantalla la embebe con un `<iframe>` o con el Web Component (o la abre en una ventana propia) y escucha los mensajes del widget.

> **La API key del integrador nunca debe llegar al navegador.** El `token` del fragmento (`#t=`) es otra cosa: es una credencial acotada a **esa** solicitud, de una hora de vida (`FIRMADOC_SIGNING_TOKEN_TTL_SECONDS`), que solo sirve para los endpoints del widget. Va en el fragmento para que el navegador no lo envíe al servidor, no aparezca en registros de acceso ni en el `Referer`; el widget lo guarda solo en memoria y lo borra de la barra de direcciones y del historial al cargar.

### Opción 1: iframe (recomendada)

```html
<iframe
  src="https://firmadoc.example.org/sign/b3f1c2e0-...#t=eyJ..."
  title="Firma de documento (Firmadoc)"
  width="480" height="760"
  allow="local-network-access; local-network; loopback-network"
  sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox"
  referrerpolicy="no-referrer"></iframe>
```

- `allow`: delega el permiso de **acceso a la red local** al iframe, necesario para que el widget hable con el agente en `127.0.0.1` desde Chrome/Edge 142+. El nombre de la política cambió entre versiones del navegador; los desconocidos se ignoran, por eso se listan todos. Verificarlo con el navegador instalado.
- Si el sistema anfitrión pasa el HTML por un sanitizador o gestor de contenido, comprobá en el DOM ya renderizado que el atributo `allow` siga presente: según fuentes secundarias, algunas plataformas lo eliminan y entonces el widget no puede hablar con el agente. Firefox y Safari no están verificados.
- `sandbox`: `allow-same-origin` es necesario para que el widget llame a su propio servidor; `allow-downloads` para el botón "Descargar PDF firmado".
- Solo se puede embeber desde los orígenes del integrador (`allowed_origins`): el servidor responde `Content-Security-Policy: frame-ancestors <orígenes>`. Desde cualquier otro origen el navegador bloquea el marco.

### Opción 2: Web Component

```html
<script src="https://firmadoc.example.org/widget.js"></script> <!-- una sola vez -->
<firmadoc-widget signing-url="https://firmadoc.example.org/sign/b3f1c2e0-...#t=eyJ..."></firmadoc-widget>
```

Es un **envoltorio del iframe** (mismo aislamiento, sin CORS ni estilos filtrados). Tamaño por defecto 480 × 760; se cambia con CSS (`firmadoc-widget { height: 640px }`). Reemite los mensajes como eventos DOM: `firmadoc-ready`, `firmadoc-signed`, `firmadoc-failed`, `firmadoc-cancelled`, `firmadoc-closed` (el mensaje original va en `event.detail`). Solo reemite lo que viene de **su propio iframe** y del **origen de la `signing-url`**. Si se cambia el atributo `signing-url`, recarga.

### Opción 3: ventana emergente (alternativa)

```js
// En un gesto del usuario (clic): fuera de él, el navegador bloquea la ventana.
const popup = window.open(signingUrl, "firmadoc-firma", "popup,width=560,height=860");
if (!popup) { /* bloqueada: pedir que la permita, o caer al iframe */ }
window.addEventListener("message", (event) => {
  if (event.source !== popup) return;                           // la ventana que abrimos
  if (event.origin !== "https://firmadoc.example.org") return;  // el origen de Firmadoc
  if (event.data?.source !== "firmadoc") return;
  // ...
});
```

El widget corre como **página principal** de esa ventana y avisa por `window.opener` con los mismos mensajes y el
mismo destinatario explícito por origen permitido (una ventana abierta desde otro origen no recibe nada). «Cerrar»
cierra la ventana; para detectar que la persona la cerró antes, consultá `popup.closed`. Cuándo conviene: cuando el
anfitrión no puede delegar el permiso de acceso a la red local (elimina el atributo `allow` o no lo admite), porque
aquí el permiso se le pide al origen de Firmadoc directamente, y cuando se quiere evitar un módulo dentro de un
diálogo. Costos: hay que abrirla en un gesto del usuario, la persona sale momentáneamente de la aplicación y, con
`noopener`, no hay forma de avisar (el resultado se consulta igual desde el backend con la API key). El panel de
Firmadoc (`frontend/src/app/sections/widget-window.ts`) usa este modo, con el iframe en un diálogo como respaldo si
la ventana fue bloqueada.

## Mensajes hacia la página anfitriona

El widget avisa con `postMessage` a la página que lo embebe (`window.parent`) o, en una ventana propia, a la que lo abrió (`window.opener`), siempre con `targetOrigin` explícito (uno por cada origen de `allowed_origins`; **nunca `"*"`**) y nunca incluye el token ni el PDF:

| `type` | Cuándo | Campos extra |
|---|---|---|
| `firmadoc:ready` | cargó el contexto de la solicitud | — |
| `firmadoc:signed` | la firma se completó | `document`: `id`, `version_number`, `is_active_version`, `signing_status`, `signature_level` |
| `firmadoc:batch-completed` | un lote terminó (solo en `/sign/batch/{id}`) | `batchId`, `status`, `signed`, `total` y `documents[]` con `document_id`, `status`, `version_number` |
| `firmadoc:failed` | error irrecuperable | `code` (sin detalles internos) |
| `firmadoc:cancelled` | la persona canceló antes de firmar | — |
| `firmadoc:closed` | la persona cerró la pantalla de resultado | — |

Todos llevan `{ source: "firmadoc", type, requestId }` (en un lote, `requestId` es el id del lote). El widget **no acepta mensajes entrantes**. Para saber el resultado de forma confiable, el backend del integrador debe consultar la solicitud con su API key (`GET /api/v1/signature-requests/{id}`): el mensaje del navegador es solo para actualizar la interfaz.

**Siempre validá el emisor** en la página anfitriona:

```js
window.addEventListener("message", (event) => {
  if (event.source !== iframe.contentWindow) return;      // la ventana del iframe
  if (event.origin !== "https://firmadoc.example.org") return; // el origen de Firmadoc
  if (event.data?.source !== "firmadoc") return;
  // ...
});
```

## Guía para Angular

**1. El backend entrega la `signing_url`** (Angular nunca conoce la API key):

```ts
// signature.service.ts
@Injectable({ providedIn: "root" })
export class SignatureService {
  constructor(private http: HttpClient) {}
  /** Tu propio backend crea la solicitud en Firmadoc con la API key y devuelve la signing_url. */
  start(documentId: string) {
    return this.http.post<{ signingUrl: string }>(`/api/documentos/${documentId}/firmar`, {});
  }
}
```

**2. Componente con iframe** (hace falta `DomSanitizer`: Angular rechaza URLs de iframe sin sanear):

```ts
// firmar-documento.component.ts
import { Component, ElementRef, HostListener, Input, ViewChild } from "@angular/core";
import { DomSanitizer, SafeResourceUrl } from "@angular/platform-browser";

@Component({
  selector: "app-firmar-documento",
  standalone: true,
  template: `
    <iframe #frame *ngIf="url"
      [src]="url"
      title="Firma de documento (Firmadoc)"
      width="480" height="760"
      allow="local-network-access; local-network; loopback-network"
      sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox"
      referrerpolicy="no-referrer"></iframe>`,
})
export class FirmarDocumentoComponent {
  @ViewChild("frame") frame?: ElementRef<HTMLIFrameElement>;
  url?: SafeResourceUrl;
  private firmadocOrigin = "";

  constructor(private sanitizer: DomSanitizer) {}

  @Input() set signingUrl(value: string) {
    this.firmadocOrigin = new URL(value).origin;
    // Es seguro sanear porque la URL la entrega TU backend, no el usuario.
    this.url = this.sanitizer.bypassSecurityTrustResourceUrl(value);
  }

  @HostListener("window:message", ["$event"])
  onMessage(event: MessageEvent) {
    if (event.source !== this.frame?.nativeElement.contentWindow) return; // ventana del iframe
    if (event.origin !== this.firmadocOrigin) return; // origen de Firmadoc
    if (event.data?.source !== "firmadoc") return;
    if (event.data.type === "firmadoc:signed") {
      // actualizar la pantalla; el estado definitivo se confirma contra tu backend
    }
  }
}
```

**3. O con el Web Component**: agregar `CUSTOM_ELEMENTS_SCHEMA` al módulo o componente standalone y cargar `widget.js` una sola vez (`index.html` o `angular.json → scripts`):

```ts
@Component({
  selector: "app-firmar-documento",
  standalone: true,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  template: `<firmadoc-widget [attr.signing-url]="signingUrl" (firmadoc-signed)="onSigned($event)"></firmadoc-widget>`,
})
export class FirmarDocumentoComponent {
  @Input() signingUrl = "";
  onSigned(event: Event) {
    console.log((event as CustomEvent).detail.document);
  }
}
```

> El proyecto no incluye una aplicación Angular de prueba; esta guía se verificó contra la página anfitriona `examples/host.html` (mismos mensajes, mismas validaciones). Un componente Angular concreto puede requerir ajustes de `DomSanitizer` o del `Content-Security-Policy` de la aplicación.

**4. O en una ventana propia** (sin iframe ni delegación del permiso de red local). Abrila en el `click`:

```ts
// firmar-en-ventana.component.ts
@Component({ selector: "app-firmar-en-ventana", standalone: true, template: `<button (click)="abrir()">Firmar</button>` })
export class FirmarEnVentanaComponent {
  @Input() signingUrl = "";
  private popup: Window | null = null;

  abrir() {
    this.popup = window.open(this.signingUrl, "firmadoc-firma", "popup,width=560,height=860");
    if (!this.popup) alert("Permití las ventanas emergentes para firmar."); // o caer al iframe
  }

  @HostListener("window:message", ["$event"])
  onMessage(event: MessageEvent) {
    if (!this.popup || event.source !== this.popup) return; // la ventana que abrimos
    if (event.origin !== new URL(this.signingUrl).origin) return; // origen de Firmadoc
    if (event.data?.source !== "firmadoc") return;
    if (event.data.type === "firmadoc:signed") {
      // actualizar la pantalla; el estado definitivo se confirma contra tu backend
    }
  }
}
```

El ejemplo completo, con detección de la ventana cerrada y el diálogo como respaldo, está en el panel de Firmadoc:
`frontend/src/app/sections/widget-window.ts` y `sign.ts`.

## Configuración del servidor

| Variable | Por defecto | Uso |
|---|---|---|
| `FIRMADOC_SIGNING_SECRET` | *(efímero)* | secreto HMAC de los tokens, **mínimo 32 caracteres**. En producción es obligatorio fijarlo: con el efímero los enlaces dejan de valer al reiniciar |
| `FIRMADOC_SIGNING_TOKEN_TTL_SECONDS` | `3600` | vida del token del widget |
| `FIRMADOC_AGENT_URL` | `http://127.0.0.1:47123` | dónde busca el widget al agente local (también entra en `connect-src` de la CSP) |
| `FIRMADOC_WIDGET_DIST` | `widget/dist` | widget compilado que sirve el servidor |
| `FIRMADOC_PUBLIC_BASE_URL` | `http://localhost:8000` | base de la `signing_url` |

El agente local debe tener el **origen del widget** (el de `FIRMADOC_PUBLIC_BASE_URL`) en su lista `allowed_origins`; y el sistema integrador debe tener su propio origen en `allowed_origins` del integrador (para `frame-ancestors` y `postMessage`). Ver `agent/README.md`.

El servidor entrega la página con `Content-Security-Policy` estricta (`default-src 'none'`, `script-src 'self'`, sin `unsafe-inline`), `Referrer-Policy: no-referrer` y `Cache-Control: no-store`. Por eso el widget **no usa estilos ni scripts en línea**.

## Desarrollo

```powershell
cd widget
$env:NODE_USE_SYSTEM_CA = "1"   # solo si la red intercepta TLS (ver más abajo)
npm install
npm run dev          # http://localhost:5173 con proxy de /api hacia 127.0.0.1:8000
npm test             # Vitest: estado, clientes, pantallas, accesibilidad, mensajes
npm run typecheck && npm run lint
npm run build        # genera dist/ (SPA + widget.js) que sirve el servidor
```

- `dist/index.html` + `dist/assets/*` (SPA, servidos bajo `/widget-assets/`) y `dist/widget.js` (Web Component).
- `examples/host.html`: página anfitriona de ejemplo (`#signing_url=<url>&mode=iframe|component`).
- Si `npm install` falla con `SELF_SIGNED_CERT_IN_CHAIN` (red corporativa que intercepta TLS), usá `NODE_USE_SYSTEM_CA=1` (Node 22.15+/24) en vez de desactivar la verificación (`strict-ssl=false`).

Estructura (`src/`): `api/` (clientes tipados del servidor y del agente, errores normalizados), `state/` (máquina de estados pura y el hook que orquesta), `screens/` y `components/` (interfaz), `messages/es.ts` (todos los textos de error), `embed/` (mensajes al anfitrión y Web Component), `bootstrap/` (lectura del token).

## Prueba de punta a punta

`pytest tests/e2e` levanta el servidor y el agente reales, sirve una página anfitriona en **otro origen** y recorre el widget en un Chrome real (Playwright, con el Chrome del sistema), incluido el bloqueo del iframe desde un origen no permitido. Requiere haber ejecutado `npm run build`; se omite si faltan el widget compilado o Chrome.

## Elegir el método de firma

Al crear la solicitud, el integrador puede enviar `allowed_providers` (por ejemplo `["token", "local"]`, con
`provider` como método inicial). Con más de un método el widget abre en "¿Cómo querés firmar?"; la elección se
confirma en el servidor (`POST /api/v1/widget/requests/{id}/provider`, solo con la solicitud `pending`) y queda en
la auditoría (`provider_selected`). Mientras no se haya preparado la firma, las pantallas de espera o error
ofrecen "Elegir otro método". Sin `allowed_providers` la solicitud admite solo `provider`, como antes.

Con `firmar` el widget envía el documento al servicio, muestra el enlace "Continuar en el servicio de firma" (se
abre en otra pestaña) y consulta el estado hasta que llega el resultado (ver `docs/firmar.md`).
