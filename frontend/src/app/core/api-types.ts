/** Respuestas de la API de administración (`/api/v1/admin`); solo los campos que usa el panel. */

export interface Page<T> {
  items: T[];
  total: number;
}

export type RequestOrigin = { kind: 'individual' } | { kind: 'batch'; batch_id: string; label: string };

export interface RequestItem {
  id: string;
  created_at: string;
  status: string;
  provider: string;
  integrating_system: { id: string; name: string };
  document: {
    id: string;
    external_document_id: string | null;
    signing_status: string;
    current_version_number: number | null;
    signature_deadline: string | null;
  };
  signer: { name: string; identifier: string };
  certificate: { subject: string } | null;
  origin: RequestOrigin;
}

export interface DocumentVersion {
  version_number: number;
  origin: string;
  signature_level: string | null;
  is_current: boolean;
  document_hash: string;
  created_at: string;
}

export interface TimelineEntry {
  at: string;
  actor: string;
  title: string;
  detail: string | null;
  kind: string;
}

export interface Technical {
  transaction_id: string;
  provider: string;
  signature_level: string | null;
  certificate: { subject: string; issuer_subject: string; serial_number: string } | null;
  original_hash: string | null;
  signed_hash: string | null;
  signer: { name: string; identifier: string } | null;
}

export interface Custody {
  document: {
    id: string;
    external_document_id: string | null;
    signing_status: string;
    signature_deadline: string | null;
    integrating_system_name: string | null;
  };
  versions: DocumentVersion[];
  timeline: TimelineEntry[];
  technical: Technical | null;
}

export interface WebhookDelivery {
  id: string;
  created_at: string;
  event_type: string;
  url: string;
  status: string;
  attempts: number;
  next_attempt_at: string | null;
  last_error: string | null;
  response_status: number | null;
}

export interface AdminEvent {
  id: string;
  created_at: string;
  actor: string;
  action: string;
  detail: unknown;
}

export interface TrustAnchor {
  is_root: boolean;
  subject: string;
  not_after: string;
  fingerprint: string;
}

export interface LocalCertificate {
  current: { subject: string; serial_number: string; not_after: string } | null;
  archived: { serial_number: string; fingerprint: string; not_after: string }[];
}

export interface Integrator {
  id: string;
  name: string;
  allowed_origins: string[];
  has_webhook_secret: boolean;
  status: 'active' | 'disabled';
  internal: boolean;
  created_at: string;
}

export interface SigningUpload {
  request_id: string;
  document_id: string;
  signing_url: string;
  filename: string;
  page_count: number;
  size_bytes: number;
  document_hash: string;
}

export interface BatchDocument {
  document_id: string;
  document_hash: string;
  filename: string;
  page_count: number;
  size_bytes: number;
}

export interface SigningBatchUpload {
  batch_id: string;
  signing_url: string;
  documents: BatchDocument[];
}
