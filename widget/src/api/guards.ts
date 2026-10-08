/** Guardas mínimas: no se confía ciegamente en la forma de lo que responden el servidor o el agente. */

import type {
  AgentCertificate,
  AgentSignature,
  Challenge,
  PrepareResponse,
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
    isString(x.agent_url)
  );
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

export function isPrepareResponse(x: unknown): x is PrepareResponse {
  return isObject(x) && Array.isArray(x.challenges) && x.challenges.every(isChallenge);
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
