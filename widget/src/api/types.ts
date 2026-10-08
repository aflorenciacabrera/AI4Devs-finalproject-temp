/** Tipos de los contratos con el servidor (API del widget) y con el agente local. */

export type Provider = "token" | "local" | "firmar";

export interface DocumentBlock {
  id: string;
  external_document_id: string | null;
  version_number: number;
  is_active_version: boolean;
  signing_status: string;
  signature_level: string | null;
  download_url: string;
  signed_document_base64: string | null;
}

export interface WidgetCertificate {
  subject: string;
  issuer_subject: string;
  serial_number: string;
}

/** Un documento de un lote, tal como lo muestra el widget (sin binarios). */
export interface BatchDocument {
  signature_request_id: string;
  document_id: string;
  document_name: string;
  page_count: number | null;
  size_bytes: number | null;
  status: string;
  version_number: number | null;
  error: { code: string | null; detail: string; http_status: number } | null;
}

/** El lote visto desde el widget: lista de documentos y estado del lote. */
export interface BatchInfo {
  status: string; // pending | signing | completed | partial_failure | failed
  documents: BatchDocument[];
}

export interface WidgetContext {
  id: string;
  status: "pending" | "signing" | "signed" | "failed";
  provider: Provider | string;
  document_name: string;
  signer_name: string;
  allowed_origins: string[];
  agent_url: string;
  /** Métodos que la persona puede elegir; con uno solo no hay pantalla de elección. */
  allowed_providers: string[];
  token_expires_at: string;
  signed_at: string | null;
  certificate: WidgetCertificate | null;
  document: DocumentBlock | null;
  /** Estado del documento (firma individual) para la tarjeta del documento. */
  signing_status?: string | null;
  signature_deadline?: string | null;
  page_count?: number | null;
  size_bytes?: number | null;
  /** Presente solo en el widget de un lote. */
  batch?: BatchInfo;
}

/** Respuesta del servidor para un lote (`/api/v1/widget/batches/{id}`). */
export interface BatchContextResponse {
  id: string;
  status: string;
  provider: string;
  allowed_providers: string[];
  signer_name: string;
  allowed_origins: string[];
  agent_url: string;
  token_expires_at: string;
  completed_at: string | null;
  documents: BatchDocument[];
}

export interface RetryResponse {
  id: string;
  signing_url: string;
}

export interface Challenge {
  challenge_id: string;
  document_name: string;
  hash_algorithm: string;
  hash_to_sign: string;
}

export interface RemoteInfo {
  operation_id: string;
  authorization_url: string;
}

export interface PrepareResponse {
  challenges: Challenge[];
  expires_at: string;
  /** Solo con la firma remota (`firmar`): la operación abierta en el servicio. */
  remote?: RemoteInfo | null;
}

export interface AgentCertificate {
  id: string;
  token_label: string;
  subject: string;
  issuer: string;
  serial_number: string;
  not_before: string;
  not_after: string;
  certificate_pem: string;
}

export interface AgentSignature {
  challenge_id: string;
  signature_base64: string;
}
