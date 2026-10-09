import { Component, ElementRef, HostListener, Injector, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { FileUpload } from 'primeng/fileupload';
import { Message } from 'primeng/message';
import { Tag } from 'primeng/tag';
import { Timeline } from 'primeng/timeline';
import { AdminApi } from '../core/admin-api';
import { BatchDocument, SigningBatchUpload, SigningUpload } from '../core/api-types';
import { MAX_PDF_BYTES, SizePipe, formatSize, isPdf, pagesLabel } from '../core/format';

export interface Ready {
  name: string;
  meta: string;
  url: SafeResourceUrl;
  /** Origen de la `signing_url`: el único del que se aceptan mensajes del widget. */
  origin: string;
  documents: BatchDocument[] | null;
}

export interface SignResult {
  text: string;
  severity: 'success' | 'error';
}

export interface Step {
  icon: string;
  title: string;
  text: string;
}

export const STEPS: Step[] = [
  { icon: 'pi pi-upload', title: 'Cargá el PDF', text: 'Queda guardado como versión original (v1).' },
  { icon: 'pi pi-sliders-h', title: 'Elegí el método de firma', text: 'Con token, remota o propia (demostración).' },
  {
    icon: 'pi pi-key',
    title: 'Elegí el certificado y confirmá con el PIN',
    text: 'El PIN se ingresa en tu PC, en Firmadoc Agent.',
  },
  {
    icon: 'pi pi-download',
    title: 'Descargá el documento firmado',
    text: 'Queda como nueva versión vigente; el original se conserva.',
  },
];

interface WidgetMessage {
  source?: unknown;
  type?: unknown;
  signed?: unknown;
  total?: unknown;
  code?: unknown;
}

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.onerror = () => reject(new Error('No se pudo leer el archivo.'));
    reader.readAsDataURL(file);
  });
}

/**
 * Carga de uno o varios PDF (p-fileupload con plantillas propias) y widget de firma embebido. Es el ejemplo de
 * referencia de cómo una aplicación Angular integra el widget: iframe con `sandbox`/`allow`/`referrerpolicy` y
 * mensajes validados por ventana y origen.
 */
@Component({
  selector: 'app-sign',
  imports: [FileUpload, Button, Card, Tag, Timeline, Message, SizePipe],
  templateUrl: './sign.html',
})
export class Sign {
  private readonly api = inject(AdminApi);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly injector = inject(Injector);

  readonly uploader = viewChild<FileUpload>('uploader');
  readonly frame = viewChild<ElementRef<HTMLIFrameElement>>('frame');

  readonly maxBytes = MAX_PDF_BYTES;
  readonly steps = STEPS;
  readonly uploading = signal(false);
  readonly ready = signal<Ready | null>(null);
  readonly result = signal<SignResult | null>(null);

  pages = pagesLabel;

  uploadLabel(count: number): string {
    return count > 1 ? `Cargar y firmar ${count} documentos` : 'Cargar y firmar documento';
  }

  summary(files: File[]): string {
    const total = files.reduce((sum, f) => sum + f.size, 0);
    return `${files.length} ${files.length === 1 ? 'archivo' : 'archivos'} · ${formatSize(total)}`;
  }

  /** Valida en el navegador y envía uno (carga individual) o varios (lote) PDF. */
  async upload(files: File[]): Promise<void> {
    if (files.length === 0 || this.uploading()) return;
    const bad = files.find((f) => !isPdf(f));
    if (bad) {
      this.api.fail(new Error(`«${bad.name}» no es un PDF: solo se pueden cargar archivos PDF.`), 'Archivo no válido');
      return;
    }
    const big = files.find((f) => f.size > MAX_PDF_BYTES);
    if (big) {
      this.api.fail(new Error(`«${big.name}» supera el tamaño máximo de ${formatSize(MAX_PDF_BYTES)}.`), 'Archivo no válido');
      return;
    }
    this.uploading.set(true);
    try {
      const documents = [];
      for (const file of files) documents.push({ filename: file.name, document_base64: await readBase64(file) });
      if (documents.length === 1) {
        const data = await this.api.request<SigningUpload>('POST', '/signing-uploads', documents[0]);
        this.show(data.filename, `${pagesLabel(data.page_count)} · ${formatSize(data.size_bytes)}`, data.signing_url, null);
      } else {
        const data = await this.api.request<SigningBatchUpload>('POST', '/signing-batch-uploads', { documents });
        this.show(`${data.documents.length} documentos`, 'Firma en lote: un solo PIN para todos', data.signing_url, data.documents);
      }
      this.uploader()?.clear();
    } catch (error) {
      this.api.fail(error, 'No se pudo cargar');
    } finally {
      this.uploading.set(false);
    }
  }

  reset(): void {
    this.ready.set(null);
    this.result.set(null);
  }

  replace(): void {
    this.reset();
    afterNextRender(() => this.uploader()?.choose(), { injector: this.injector });
  }

  /** Solo se atienden mensajes de la ventana del iframe y del origen de la `signing_url`. */
  @HostListener('window:message', ['$event'])
  onMessage(event: MessageEvent): void {
    const frame = this.frame()?.nativeElement;
    const ready = this.ready();
    if (!frame || !ready || event.source !== frame.contentWindow || event.origin !== ready.origin) return;
    const data = event.data as WidgetMessage | null;
    if (!data || typeof data !== 'object' || data.source !== 'firmadoc') return;
    switch (data.type) {
      case 'firmadoc:signed':
        this.result.set({
          severity: 'success',
          text: 'Documento firmado: quedó como nueva versión vigente. Descargalo desde el módulo de firma.',
        });
        break;
      case 'firmadoc:batch-completed': {
        const signed = Number(data.signed) || 0;
        const total = Number(data.total) || 0;
        const all = signed === total;
        this.result.set({
          severity: all ? 'success' : 'error',
          text: `${signed} de ${total} documentos firmados.` + (all ? '' : ' Podés reintentar los fallidos desde el módulo de firma.'),
        });
        break;
      }
      case 'firmadoc:failed':
        this.result.set({ severity: 'error', text: `La firma falló${data.code ? ` (${String(data.code)})` : ''}.` });
        break;
      case 'firmadoc:cancelled':
        this.result.set({ severity: 'error', text: 'Firma cancelada. El documento quedó guardado sin firmar.' });
        break;
    }
  }

  private show(name: string, meta: string, signingUrl: string, documents: BatchDocument[] | null): void {
    this.result.set(null);
    this.ready.set({
      name,
      meta,
      // Seguro: la signing_url la entrega el propio backend de Firmadoc, no la persona.
      url: this.sanitizer.bypassSecurityTrustResourceUrl(signingUrl),
      origin: new URL(signingUrl, location.href).origin,
      documents,
    });
  }
}
