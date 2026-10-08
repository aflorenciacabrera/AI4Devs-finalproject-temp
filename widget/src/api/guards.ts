/** Guardas mínimas: no se confía ciegamente en la forma de lo que responden el servidor o el agente. */

import type {
  AgentCertificate,
  AgentSignature,
  BatchContextResponse,
  Challenge,
  PrepareResponse,
  RetryResponse,
  WidgetContext,
} from "./types";

const isObject = (x: unknown): x is Record<string, unknown> =>
  typeof x === "object" && x !== null && !Array.isArray(x);
const isString = (x: unknown): x is string => typeof x === "string";

export function isWidgetContext(x: unknown): x is WidgetContext {
  return (
    isObject(x) &&
    isString(x.id) &&
    isString(x.status) &&
    isString(x.provider) &&
    isString(x.document_name) &&
    isString(x.signer_name) &&
    Array.isArray(x.allowed_origins) &&
    x.allowed_origins.every(isString) &&
    Array.isArray(x.allowed_providers) &&
    x.allowed_providers.every(isString) &&
    isString(x.agent_url)
  );
}

export function isBatchContext(x: unknown): x is BatchContextResponse {
  return (
    isObject(x) &&
    isString(x.id) &&
    isString(x.status) &&
    isString(x.provider) &&
    isString(x.signer_name) &&
    Array.isArray(x.allowed_origins) &&
    x.allowed_origins.every(isString) &&
    Array.isArray(x.allowed_providers) &&
    x.allowed_providers.every(isString) &&
    isString(x.agent_url) &&
    Array.isArray(x.documents) &&
    x.documents.every((d) => isObject(d) && isString(d.signature_request_id) && isString(d.document_name) && isString(d.status))
  );
}

export function isRetryResponse(x: unknown): x is RetryResponse {
  return isObject(x) && isString(x.id) && isString(x.signing_url);
}

function isChallenge(x: unknown): x is Challenge {
  return (
    isObject(x) &&
    isString(x.challenge_id) &&
    isString(x.document_name) &&
    isString(x.hash_algorithm) &&
    isString(x.hash_to_sign)
  );
}

function isRemote(x: unknown): boolean {
  return x === undefined || x === null || (isObject(x) && isString(x.operation_id) && isString(x.authorization_url));
}

export function isPrepareResponse(x: unknown): x is PrepareResponse {
  return isObject(x) && Array.isArray(x.challenges) && x.challenges.every(isChallenge) && isRemote(x.remote);
}

export function isAgentCertificate(x: unknown): x is AgentCertificate {
  return (
    isObject(x) &&
    isString(x.id) &&
    isString(x.subject) &&
    isString(x.issuer) &&
    isString(x.not_before) &&
    isString(x.not_after) &&
    isString(x.certificate_pem)
  );
}

export function isAgentSignatures(x: unknown): x is { signatures: AgentSignature[] } {
  return (
    isObject(x) &&
    Array.isArray(x.signatures) &&
    x.signatures.every(
      (s) => isObject(s) && isString(s.challenge_id) && isString(s.signature_base64),
    )
  );
}
