/** Máquina de estados del widget: una función pura, sin DOM ni red, fácil de probar. */

import type { AgentCertificate, Challenge, WidgetContext } from "../api/types";

type Ctx = { context: WidgetContext };
type WithCerts = Ctx & { certificates: AgentCertificate[] };
type WithCert = WithCerts & { certificate: AgentCertificate };

export type State =
  | { name: "loading" }
  | { name: "invalid_link" }
  | ({ name: "unsupported" } & Ctx)
  | ({ name: "confirm_local" } & Ctx)
  | ({ name: "working_local" } & Ctx)
  | ({ name: "detecting_agent" } & Ctx)
  | ({ name: "agent_missing" } & Ctx)
  | ({ name: "agent_problem"; code: string } & Ctx)
  | ({ name: "choose_certificate"; selectedId: string | null; notice?: "cancelled" } & WithCerts)
  | ({ name: "validating" } & WithCert)
  | ({ name: "cert_rejected"; code: string } & WithCert)
  | ({ name: "awaiting_pin"; challenges: Challenge[] } & WithCert)
  | ({ name: "pin_error"; kind: "pin_incorrect" | "pin_expired" | "busy"; challenges: Challenge[] } & WithCert)
  | ({ name: "pin_locked" } & Ctx)
  | ({ name: "completing"; challenges: Challenge[] } & WithCert)
  | ({ name: "time_expired" } & WithCert)
  | ({ name: "success" } & Ctx)
  | ({ name: "failed"; code: string } & Partial<Ctx>)
  | ({ name: "cancelled" } & Partial<Ctx>);

export type Event =
  | { type: "context_loaded"; context: WidgetContext }
  | { type: "link_invalid" }
  | { type: "agent_detecting" }
  | { type: "agent_unreachable" }
  | { type: "agent_problem"; code: string }
  | { type: "certificates"; certificates: AgentCertificate[] }
  | { type: "select"; id: string }
  | { type: "validating" }
  | { type: "revalidate" }
  | { type: "rejected"; code: string }
  | { type: "awaiting_pin"; challenges: Challenge[] }
  | { type: "pin_error"; kind: "pin_incorrect" | "pin_expired" | "busy" }
  | { type: "pin_locked" }
  | { type: "user_cancelled" }
  | { type: "completing" }
  | { type: "time_expired" }
  | { type: "choose_another" }
  | { type: "local_working" }
  | { type: "success"; context: WidgetContext }
  | { type: "failed"; code: string }
  | { type: "cancelled" };

export const initialState: State = { name: "loading" };

const hasContext = (s: State): s is State & Ctx => "context" in s && s.context !== undefined;
const hasCert = (s: State): s is State & WithCert => "certificate" in s;

/** ¿El certificado ya venció? (la lista los deshabilita, pero la última palabra la tiene el servidor.) */
export function isExpired(cert: AgentCertificate, now: Date): boolean {
  return new Date(cert.not_after).getTime() < now.getTime();
}

function firstUsable(certs: AgentCertificate[], now: Date): string | null {
  return certs.find((c) => !isExpired(c, now))?.id ?? null;
}

export function reducer(state: State, event: Event, now: Date = new Date()): State {
  switch (event.type) {
    case "context_loaded": {
      const { context } = event;
      if (context.status === "signed") return { name: "success", context };
      if (context.status === "failed") return { name: "failed", code: "request_failed", context };
      if (context.provider === "local") return { name: "confirm_local", context };
      if (context.provider === "token") return { name: "detecting_agent", context };
      return { name: "unsupported", context };
    }
    case "link_invalid":
      return { name: "invalid_link" };
    case "agent_detecting":
      return hasContext(state) && context(state).provider === "token"
        ? { name: "detecting_agent", context: context(state) }
        : state;
    case "agent_unreachable":
      return hasContext(state) ? { name: "agent_missing", context: context(state) } : state;
    case "agent_problem":
      return hasContext(state)
        ? { name: "agent_problem", code: event.code, context: context(state) }
        : state;
    case "certificates":
      return hasContext(state)
        ? {
            name: "choose_certificate",
            context: context(state),
            certificates: event.certificates,
            selectedId: firstUsable(event.certificates, now),
          }
        : state;
    case "select":
      return state.name === "choose_certificate" ? { ...state, selectedId: event.id } : state;
    case "validating": {
      if (state.name !== "choose_certificate") return state;
      const certificate = state.certificates.find((c) => c.id === state.selectedId);
      if (!certificate) return state;
      return {
        name: "validating",
        context: state.context,
        certificates: state.certificates,
        certificate,
      };
    }
    case "revalidate":
      return state.name === "time_expired"
        ? {
            name: "validating",
            context: state.context,
            certificates: state.certificates,
            certificate: state.certificate,
          }
        : state;
    case "rejected":
      return state.name === "validating" ? { ...state, name: "cert_rejected", code: event.code } : state;
    case "awaiting_pin":
      return state.name === "validating" ||
        state.name === "pin_error" ||
        state.name === "time_expired"
        ? {
            name: "awaiting_pin",
            context: state.context,
            certificates: state.certificates,
            certificate: state.certificate,
            challenges: event.challenges,
          }
        : state;
    case "pin_error":
      return state.name === "awaiting_pin" ? { ...state, name: "pin_error", kind: event.kind } : state;
    case "pin_locked":
      return hasContext(state) ? { name: "pin_locked", context: context(state) } : state;
    case "user_cancelled":
      return state.name === "awaiting_pin" || state.name === "pin_error"
        ? {
            name: "choose_certificate",
            context: state.context,
            certificates: state.certificates,
            selectedId: state.certificate.id,
            notice: "cancelled",
          }
        : state;
    case "completing":
      return state.name === "awaiting_pin" ? { ...state, name: "completing" } : state;
    case "time_expired":
      return (state.name === "completing" || state.name === "awaiting_pin") && hasCert(state)
        ? {
            name: "time_expired",
            context: state.context,
            certificates: state.certificates,
            certificate: state.certificate,
          }
        : state;
    case "choose_another":
      return state.name === "cert_rejected" || state.name === "time_expired"
        ? {
            name: "choose_certificate",
            context: state.context,
            certificates: state.certificates,
            selectedId: firstUsable(
              state.certificates.filter((c) => c.id !== state.certificate.id),
              now,
            ),
          }
        : state;
    case "local_working":
      return state.name === "confirm_local" ? { name: "working_local", context: state.context } : state;
    case "success":
      return { name: "success", context: event.context };
    case "failed":
      return { name: "failed", code: event.code, ...(hasContext(state) ? { context: context(state) } : {}) };
    case "cancelled":
      return { name: "cancelled", ...(hasContext(state) ? { context: context(state) } : {}) };
  }
}

function context(state: State & Ctx): WidgetContext {
  return state.context;
}

/** Pantallas en las que todavía se puede cancelar (antes de que la firma esté hecha). */
export function isCancellable(state: State): boolean {
  return [
    "confirm_local",
    "detecting_agent",
    "agent_missing",
    "agent_problem",
    "choose_certificate",
    "cert_rejected",
    "pin_error",
    "time_expired",
    "unsupported",
  ].includes(state.name);
}
