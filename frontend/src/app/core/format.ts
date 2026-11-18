import { Pipe, PipeTransform } from '@angular/core';

export const MAX_PDF_BYTES = 20 * 1024 * 1024;

export const STATUS_LABELS: Record<string, string> = {
  signed: 'Firmado',
  pending: 'Pendiente',
  signing: 'Firmando',
  failed: 'Fallido',
};
export const DOCUMENT_STATUS_LABELS: Record<string, string> = {
  draft: 'Borrador',
  pending_signature: 'Pendiente de firma',
  signed: 'Firmado',
};
export const PROVIDER_LABELS: Record<string, string> = { token: 'Token', local: 'Propio', firmar: 'FirmAR' };
export const DELIVERY_STATUS_LABELS: Record<string, string> = {
  pending: 'Pendiente',
  delivered: 'Entregado',
  failed: 'Fallido',
};

/** Severidad de `p-tag` para cada estado (solicitud, documento, entrega de webhook, integrador, evento). */
export type TagSeverity = 'success' | 'info' | 'warn' | 'danger' | 'secondary';
const STATUS_SEVERITY: Record<string, TagSeverity> = {
  signed: 'success',
  delivered: 'success',
  active: 'success',
  ok: 'success',
  pending: 'warn',
  signing: 'warn',
  pending_signature: 'warn',
  warning: 'warn',
  failed: 'danger',
  error: 'danger',
  disabled: 'danger',
};

export function statusSeverity(status: string): TagSeverity {
  return STATUS_SEVERITY[status] ?? 'secondary';
}

export function deliveryStatusLabel(status: string): string {
  return DELIVERY_STATUS_LABELS[status] ?? status;
}

const ISO_DATE = /^\d{4}-\d\d-\d\dT/;

/** Valor de la API como texto: fechas en es-AR, objetos como JSON, vacíos como «-». */
export function fmt(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'string' && ISO_DATE.test(value)) return new Date(value).toLocaleString('es-AR');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

export function dateOnly(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleDateString('es-AR') : '';
}

export function timeOnly(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleTimeString('es-AR') : '';
}

export function formatSize(bytes: number): string {
  return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(bytes / 1024)) + ' KB';
}

export function pagesLabel(count: number): string {
  return count + (count === 1 ? ' página' : ' páginas');
}

export function isPdf(file: { type: string; name: string }): boolean {
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name);
}

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function providerLabel(provider: string): string {
  return PROVIDER_LABELS[provider] ?? provider;
}

@Pipe({ name: 'fmt' })
export class FmtPipe implements PipeTransform {
  transform(value: unknown): string {
    return fmt(value);
  }
}

@Pipe({ name: 'dateOnly' })
export class DateOnlyPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return dateOnly(value);
  }
}

@Pipe({ name: 'timeOnly' })
export class TimeOnlyPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return timeOnly(value);
  }
}

@Pipe({ name: 'size' })
export class SizePipe implements PipeTransform {
  transform(bytes: number): string {
    return formatSize(bytes);
  }
}
