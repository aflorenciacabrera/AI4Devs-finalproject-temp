import { vi } from "vitest";

import type { AgentClient } from "../src/api/agentClient";
import type { ServerClient } from "../src/api/serverClient";
import type {
  AgentCertificate,
  Challenge,
  WidgetContext,
} from "../src/api/types";
import type { HostNotifier } from "../src/embed/hostMessages";
import type { FlowServices } from "../src/state/useSigningFlow";

export const REQUEST_ID = "11111111-2222-4333-8444-555555555555";
export const TOKEN = "TOKEN-SECRETO-DEL-WIDGET.firma";

export function makeContext(overrides: Partial<WidgetContext> = {}): WidgetContext {
  return {
    id: REQUEST_ID,
    status: "pending",
    provider: "token",
    document_name: "resolucion-0142-2026.pdf",
    signer_name: "María Fernanda Ríos",
    allowed_origins: ["https://gestor.example.org"],
    agent_url: "http://127.0.0.1:47123",
    allowed_providers: ["token"],
    token_expires_at: "2026-10-08T12:00:00Z",
    signed_at: null,
    certificate: null,
    document: null,
    ...overrides,
  };
}

export function signedContext(overrides: Partial<WidgetContext> = {}): WidgetContext {
  return makeContext({
    status: "signed",
    signed_at: "2026-10-08T10:32:07Z",
    certificate: {
      subject: "CN=María Fernanda Ríos,C=AR",
      issuer_subject: "CN=AC Demo,C=AR",
      serial_number: "3FA29C11",
    },
    document: {
      id: "doc-1",
      external_document_id: "exp-1",
      version_number: 2,
      is_active_version: true,
      signing_status: "signed",
      signature_level: "B-B",
      download_url: "http://x/documents/doc-1/versions/2/download",
      signed_document_base64: null,
    },
    ...overrides,
  });
}

export function makeCert(overrides: Partial<AgentCertificate> = {}): AgentCertificate {
  return {
    id: "SERIE1:01",
    token_label: "Token del funcionario",
    subject: "CN=María Fernanda Ríos,2.5.4.5=CUIL 27123456784,C=AR",
    issuer: "CN=AC Demo,C=AR",
    serial_number: "123456789",
    not_before: "2026-01-01T00:00:00+00:00",
    not_after: "2099-01-01T00:00:00+00:00",
    certificate_pem: "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
    ...overrides,
  };
}

export const challenge: Challenge = {
  challenge_id: "c9e1a7b4",
  document_name: "resolucion-0142-2026.pdf",
  hash_algorithm: "SHA-256",
  hash_to_sign: "q1w2e3r4t5y6u7i8o9p0a1s2d3f4g5h6j7k8l9z0x1c=",
};

export interface Fakes {
  server: { [K in keyof ServerClient]: ReturnType<typeof vi.fn> };
  agent: { [K in keyof AgentClient]: ReturnType<typeof vi.fn> };
  host: { [K in keyof HostNotifier]: ReturnType<typeof vi.fn> };
  saveFile: ReturnType<typeof vi.fn>;
  services: FlowServices;
}

export function makeFakes(context: WidgetContext = makeContext()): Fakes {
  const server = {
    getContext: vi.fn().mockResolvedValue(context),
    selectProvider: vi.fn().mockResolvedValue(context),
    prepare: vi.fn().mockResolvedValue({ challenges: [challenge], expires_at: "2099-01-01T00:00:00Z" }),
    complete: vi.fn().mockResolvedValue(signedContext({ provider: context.provider })),
    downloadPdf: vi.fn().mockResolvedValue({ blob: new Blob(["%PDF-"]), filename: "firmado.pdf" }),
  };
  const agent = {
    certificates: vi.fn().mockResolvedValue([makeCert()]),
    sign: vi.fn().mockResolvedValue([{ challenge_id: challenge.challenge_id, signature_base64: "U0lHTkFUVVJB" }]),
  };
  const host = {
    ready: vi.fn(),
    signed: vi.fn(),
    batchCompleted: vi.fn(),
    failed: vi.fn(),
    cancelled: vi.fn(),
    closed: vi.fn(),
    resized: vi.fn(),
  };
  const saveFile = vi.fn();
  return {
    server,
    agent,
    host,
    saveFile,
    services: {
      server: server as unknown as ServerClient,
      createAgent: () => agent as unknown as AgentClient,
      createHost: () => host as unknown as HostNotifier,
      saveFile,
    },
  };
}

/** Respuesta `fetch` de mentira. */
export function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}
