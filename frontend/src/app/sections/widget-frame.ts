import { Component, ElementRef, HostListener, computed, inject, input, output, signal, viewChild } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Theme, ThemeName } from '../core/theme';
import { SignResult, parseWidgetMessage, widgetFrameHeight } from '../core/widget-messages';

/**
 * Agrega `theme=<tema>&accent=blue` a la consulta de la `signing_url`, antes del fragmento (donde va el
 * token): el widget toma el modo claro/oscuro y los colores del panel.
 */
export function withTheme(signingUrl: string, theme: ThemeName): string {
  const hash = signingUrl.indexOf('#');
  const base = hash === -1 ? signingUrl : signingUrl.slice(0, hash);
  const fragment = hash === -1 ? '' : signingUrl.slice(hash);
  return `${base}${base.includes('?') ? '&' : '?'}theme=${theme}&accent=blue${fragment}`;
}

/**
 * Widget de firma embebido en la página. Es el ejemplo de referencia para integrar el widget desde Angular:
 * iframe con `sandbox`/`allow`/`referrerpolicy` y mensajes aceptados solo si vienen de la ventana del iframe y
 * del origen de la `signing_url`. El widget no dibuja marco propio, recibe el tema del panel por la URL y avisa
 * el alto de su contenido (`firmadoc:resize`), así que ocupa el ancho de la tarjeta que lo contiene y crece o
 * se achica con ella, como una parte más de la pantalla.
 */
@Component({
  selector: 'app-widget-frame',
  template: `
    <iframe
      #frame
      class="widget-frame"
      [src]="url()"
      [style.height.px]="frameHeight()"
      title="Firma de documento (Firmadoc)"
      allow="local-network-access; local-network; loopback-network"
      sandbox="allow-scripts allow-same-origin allow-downloads allow-popups allow-popups-to-escape-sandbox"
      referrerpolicy="no-referrer"></iframe>
  `,
})
export class WidgetFrame {
  private readonly sanitizer = inject(DomSanitizer);
  /** El tema se fija al abrir: cambiarlo después no recarga el widget (perdería el avance de la firma). */
  private readonly theme = inject(Theme).current();

  readonly signingUrl = input.required<string>();
  /** Cada resultado que informa el widget (firmado, lote, fallo, cancelación). */
  readonly result = output<SignResult>();
  /** La persona cerró la pantalla final del widget. */
  readonly closed = output<void>();

  readonly frame = viewChild<ElementRef<HTMLIFrameElement>>('frame');
  /** Alto que informa el widget; `null` deja el alto inicial del CSS hasta el primer aviso. */
  readonly frameHeight = signal<number | null>(null);
  /** Seguro: la signing_url la entrega el propio backend de Firmadoc, no la persona. */
  readonly url = computed<SafeResourceUrl>(() =>
    this.sanitizer.bypassSecurityTrustResourceUrl(withTheme(this.signingUrl(), this.theme)),
  );
  readonly origin = computed(() => new URL(this.signingUrl(), location.href).origin);

  @HostListener('window:message', ['$event'])
  onMessage(event: MessageEvent): void {
    const frame = this.frame()?.nativeElement;
    if (!frame || event.source !== frame.contentWindow || event.origin !== this.origin()) return;
    const height = widgetFrameHeight(event.data);
    if (height !== null) {
      this.frameHeight.set(height);
      return;
    }
    const outcome = parseWidgetMessage(event.data);
    if (!outcome) return;
    if (outcome.kind === 'closed') this.closed.emit();
    else this.result.emit(outcome.result);
  }
}
