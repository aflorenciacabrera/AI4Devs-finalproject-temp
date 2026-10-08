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

export interface WidgetContext {
  id: string;
  status: "pending" | "signing" | "signed" | "failed";
  provider: Provider | string;
  document_name: string;
  signer_name: string;
  allowed_origins: string[];
  agent_url: string;
  token_expires_at: string;
  signed_at: string | null;
  certificate: WidgetCertificate | null;
  document: DocumentBlock | null;
}

export interface Challenge {
  challenge_id: string;
  document_name: string;
  hash_algorithm: string;
  hash_to_sign: string;
}

export interface PrepareResponse {
  challenges: Challenge[];
  expires_at: string;
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
