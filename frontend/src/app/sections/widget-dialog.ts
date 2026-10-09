import { Component, ElementRef, HostListener, inject, viewChild } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { DynamicDialogConfig, DynamicDialogRef } from 'primeng/dynamicdialog';
import { SignResult, parseWidgetMessage } from '../core/widget-messages';

export interface WidgetDialogData {
  signingUrl: string;
  /** Se llama con cada resultado que informa el widget (firmado, lote, fallo, cancelación). */
  onResult: (result: SignResult) => void;
}

/**
 * Widget de firma embebido en un diálogo dinámico de PrimeNG. Es el ejemplo de referencia para integrar el
 * widget desde Angular: iframe con `sandbox`/`allow`/`referrerpolicy` y mensajes aceptados solo si vienen de la
 * ventana del iframe y del origen de la `signing_url`. Se cierra solo cuando la persona cierra el módulo.
 */
@Component({
  selector: 'app-widget-dialog',
  template: `
    <iframe
      #frame
      class="widget-frame"
      [src]="url"
      title="Firma de documento (Firmadoc)"
      allow="local-network-access; local-network; loopback-network"
      sandbox="allow-scripts allow-same-origin allow-downloads"
      referrerpolicy="no-referrer"></iframe>
  `,
})
export class WidgetDialog {
  private readonly ref = inject(DynamicDialogRef);
  private readonly data = inject(DynamicDialogConfig<WidgetDialogData>).data!;

  readonly frame = viewChild<ElementRef<HTMLIFrameElement>>('frame');
  /** Seguro: la signing_url la entrega el propio backend de Firmadoc, no la persona. */
  readonly url: SafeResourceUrl = inject(DomSanitizer).bypassSecurityTrustResourceUrl(this.data.signingUrl);
  readonly origin = new URL(this.data.signingUrl, location.href).origin;

  @HostListener('window:message', ['$event'])
  onMessage(event: MessageEvent): void {
    const frame = this.frame()?.nativeElement;
    if (!frame || event.source !== frame.contentWindow || event.origin !== this.origin) return;
    const outcome = parseWidgetMessage(event.data);
    if (!outcome) return;
    if (outcome.kind === 'closed') this.ref.close();
    else this.data.onResult(outcome.result);
  }
}
