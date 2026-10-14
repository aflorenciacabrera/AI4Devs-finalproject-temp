import { Component, DestroyRef, Injector, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { Button } from 'primeng/button';
import { Card } from 'primeng/card';
import { DialogService, DynamicDialogRef } from 'primeng/dynamicdialog';
import { FileUpload } from 'primeng/fileupload';
import { Message } from 'primeng/message';
import { Tag } from 'primeng/tag';
import { Timeline } from 'primeng/timeline';
import { AdminApi } from '../core/admin-api';
import { BatchDocument, SigningBatchUpload, SigningUpload } from '../core/api-types';
import { MAX_PDF_BYTES, SizePipe, formatSize, isPdf, pagesLabel } from '../core/format';
import { SignResult } from '../core/widget-messages';
import { WidgetDialog, WidgetDialogData } from './widget-dialog';

export interface Ready {
  name: string;
  meta: string;
  signingUrl: string;
  documents: BatchDocument[] | null;
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

export const CLOSED_WITHOUT_SIGNING: SignResult = {
  severity: 'error',
  text: 'Cerraste el módulo de firma sin firmar. El documento quedó guardado sin firmar: podés abrirlo de nuevo.',
};

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1] || '');
    reader.onerror = () => reject(new Error('No se pudo leer el archivo.'));
    reader.readAsDataURL(file);
  });
}

/** Carga de uno o varios PDF (p-fileupload con plantillas propias) y widget de firma en un diálogo dinámico. */
@Component({
  selector: 'app-sign',
  imports: [FileUpload, Button, Card, Tag, Timeline, Message, SizePipe],
  providers: [DialogService],
  templateUrl: './sign.html',
})
export class Sign {
  private readonly api = inject(AdminApi);
  private readonly dialog = inject(DialogService);
  private readonly injector = inject(Injector);
  private dialogRef: DynamicDialogRef | null = null;

  readonly uploader = viewChild<FileUpload>('uploader');

  readonly maxBytes = MAX_PDF_BYTES;
  readonly steps = STEPS;
  readonly uploading = signal(false);
  readonly ready = signal<Ready | null>(null);
  readonly result = signal<SignResult | null>(null);
  readonly widgetOpen = signal(false);

  pages = pagesLabel;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.closeWidget());
  }

  uploadLabel(count: number): string {
    return count > 1 ? `Cargar y firmar ${count} documentos` : 'Cargar y firmar documento';
  }

  summary(files: File[]): string {
    const total = files.reduce((sum, f) => sum + f.size, 0);
    return `${files.length} ${files.length === 1 ? 'archivo' : 'archivos'} · ${formatSize(total)}`;
  }

  /** Valida en el navegador y envía uno (carga individual) o varios (lote) PDF; después abre el widget. */
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

  /** Abre el widget en un diálogo dinámico de PrimeNG; los resultados se reflejan en la tarjeta. */
  openWidget(): void {
    const ready = this.ready();
    if (!ready || this.dialogRef) return;
    let reported = false;
    const data: WidgetDialogData = {
      signingUrl: ready.signingUrl,
      onResult: (result) => {
        reported = true;
        this.result.set(result);
      },
    };
    this.widgetOpen.set(true);
    const ref = this.dialog.open(WidgetDialog, {
      header: ready.name,
      data,
      modal: true,
      closable: true,
      dismissableMask: false,
      closeOnEscape: false,
      focusOnShow: false,
      styleClass: 'widget-dialog',
      width: '560px',
      style: { 'max-width': '96vw' },
      contentStyle: { padding: '0' },
    });
    if (!ref) {
      this.widgetOpen.set(false);
      return;
    }
    this.dialogRef = ref;
    ref.onClose.subscribe(() => {
      if (this.dialogRef === ref) this.dialogRef = null;
      this.widgetOpen.set(false);
      if (!reported) this.result.set(CLOSED_WITHOUT_SIGNING);
    });
  }

  closeWidget(): void {
    this.dialogRef?.close();
    this.dialogRef = null;
    this.widgetOpen.set(false);
  }

  reset(): void {
    this.closeWidget();
    this.ready.set(null);
    this.result.set(null);
  }

  replace(): void {
    this.reset();
    afterNextRender(() => this.uploader()?.choose(), { injector: this.injector });
  }

  private show(name: string, meta: string, signingUrl: string, documents: BatchDocument[] | null): void {
    this.closeWidget();
    this.result.set(null);
    this.ready.set({ name, meta, signingUrl, documents });
    this.openWidget();
  }
}
