import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Button } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { Select } from 'primeng/select';
import { TableModule } from 'primeng/table';
import { AdminApi } from '../core/admin-api';
import { Custody, Page, RequestItem } from '../core/api-types';
import {
  DOCUMENT_STATUS_LABELS,
  DateOnlyPipe,
  FmtPipe,
  TimeOnlyPipe,
  fmt,
  providerLabel,
  statusLabel,
} from '../core/format';

export const PAGE = 50;

interface Option {
  label: string;
  value: string;
}

/** Listado de documentos (solicitudes de firma) y detalle como cadena de custodia. */
@Component({
  selector: 'app-documents',
  imports: [FormsModule, Button, InputText, Select, TableModule, FmtPipe, DateOnlyPipe, TimeOnlyPipe],
  templateUrl: './documents.html',
})
export class Documents implements OnInit {
  readonly api = inject(AdminApi);

  readonly statusOptions: Option[] = [
    { label: 'Todos', value: '' },
    { label: 'Firmado', value: 'signed' },
    { label: 'Pendiente', value: 'pending' },
    { label: 'Firmando', value: 'signing' },
    { label: 'Fallido', value: 'failed' },
  ];
  readonly providerOptions: Option[] = [
    { label: 'Todos', value: '' },
    { label: 'Token', value: 'token' },
    { label: 'Propio', value: 'local' },
    { label: 'FirmAR', value: 'firmar' },
  ];
  readonly originOptions: Option[] = [
    { label: 'Todos', value: '' },
    { label: 'Individual', value: 'individual' },
    { label: 'Lote', value: 'batch' },
  ];

  readonly q = signal('');
  readonly status = signal('');
  readonly provider = signal('');
  readonly origin = signal('');
  readonly from = signal('');
  readonly to = signal('');

  readonly items = signal<RequestItem[]>([]);
  readonly total = signal(0);
  readonly offset = signal(0);
  readonly loading = signal(false);
  readonly detail = signal<Custody | null>(null);

  readonly pageText = computed(() => {
    const total = this.total();
    const from = total ? this.offset() + 1 : 0;
    return `${from}-${Math.min(this.offset() + PAGE, total)} de ${total}`;
  });
  readonly hasPrev = computed(() => this.offset() > 0);
  readonly hasNext = computed(() => this.offset() + PAGE < this.total());
  readonly currentVersion = computed(() => this.detail()?.versions.find((v) => v.is_current) ?? null);
  readonly versionsNewestFirst = computed(() => [...(this.detail()?.versions ?? [])].reverse());
  readonly technicalRows = computed<[string, string][]>(() => {
    const t = this.detail()?.technical;
    if (!t) return [['Estado', 'Todavía no hay una firma completada.']];
    return [
      ['ID de transacción', t.transaction_id],
      ['Proveedor', providerLabel(t.provider)],
      ['Nivel de firma', t.signature_level ? 'PAdES ' + t.signature_level : '-'],
      ['Certificado', t.certificate ? t.certificate.subject : '-'],
      ['Emisor', t.certificate ? `${t.certificate.issuer_subject} · serie ${t.certificate.serial_number}` : '-'],
      ['Hash original (SHA-256)', fmt(t.original_hash)],
      ['Hash documento firmado', fmt(t.signed_hash)],
      ['Firmante', t.signer ? `${t.signer.name} (${t.signer.identifier})` : '-'],
    ];
  });

  statusLabel = statusLabel;
  providerLabel = providerLabel;

  ngOnInit(): void {
    void this.load();
  }

  documentStatus(status: string): string {
    return statusLabel(status) !== status ? statusLabel(status) : (DOCUMENT_STATUS_LABELS[status] ?? status);
  }

  originLabel(r: RequestItem): string {
    return r.origin.kind === 'batch' ? 'Lote ' + r.origin.label : 'Individual';
  }

  private params(): URLSearchParams {
    const q = new URLSearchParams();
    if (this.q()) q.set('q', this.q());
    if (this.status()) q.set('status', this.status());
    if (this.provider()) q.set('provider', this.provider());
    if (this.origin()) q.set('origin', this.origin());
    if (this.from()) q.set('created_from', this.from() + 'T00:00:00Z');
    if (this.to()) q.set('created_to', this.to() + 'T23:59:59Z');
    q.set('limit', String(PAGE));
    q.set('offset', String(this.offset()));
    return q;
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const data = await this.api.request<Page<RequestItem>>('GET', '/signature-requests?' + this.params());
      this.items.set(data.items);
      this.total.set(data.total);
    } catch (error) {
      this.api.fail(error);
    } finally {
      this.loading.set(false);
    }
  }

  filter(): void {
    this.offset.set(0);
    void this.load();
  }

  prev(): void {
    if (!this.hasPrev()) return;
    this.offset.update((o) => Math.max(0, o - PAGE));
    void this.load();
  }

  next(): void {
    if (!this.hasNext()) return;
    this.offset.update((o) => o + PAGE);
    void this.load();
  }

  async open(documentId: string): Promise<void> {
    try {
      this.detail.set(await this.api.request<Custody>('GET', `/documents/${encodeURIComponent(documentId)}/custody`));
    } catch (error) {
      this.api.fail(error);
    }
  }

  back(): void {
    this.detail.set(null);
    void this.load();
  }

  async download(documentId: string, number: number): Promise<void> {
    try {
      const { blob, filename } = await this.api.download(
        `/documents/${encodeURIComponent(documentId)}/versions/${number}/download`,
      );
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename ?? `documento-v${number}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      this.api.fail(error, 'No se pudo descargar la versión');
    }
  }
}
