/**
 * Orquesta el flujo: servidor (contexto, prepare, complete) y agente (certificados, firma).
 * Toda la lógica de decisión está en `machine.ts`; acá solo están los efectos.
 */

import { useCallback, useEffect, useReducer, useRef } from "react";

import { AgentError, AgentUnreachableError, ServerError } from "../api/errors";
import type { AgentClient } from "../api/agentClient";
import type { ServerClient } from "../api/serverClient";
import type { AgentCertificate, Challenge } from "../api/types";
import { CERT_REJECTION_CODES } from "../messages/es";
import type { HostNotifier } from "../embed/hostMessages";
import { initialState, reducer, type State } from "./machine";

export interface FlowServices {
  server: ServerClient;
  /** Se crea cuando se conoce la URL del agente (la informa el servidor en el contexto). */
  createAgent: (agentUrl: string) => AgentClient;
  /** Crea el notificador cuando se conocen los orígenes permitidos. */
  createHost: (allowedOrigins: string[], requestId: string) => HostNotifier;
  saveFile: (blob: Blob, filename: string) => void;
}

export interface FlowActions {
  retryDetection(): void;
  select(id: string): void;
  validateAndContinue(): void;
  retrySign(): void;
  chooseAnother(): void;
  restartSigning(): void;
  confirmLocal(): void;
  cancel(): void;
  close(): void;
  download(): Promise<void>;
}

const isCertCode = (code: string) => (CERT_REJECTION_CODES as readonly string[]).includes(code);

export function useSigningFlow(services: FlowServices): { state: State; actions: FlowActions } {
  const [state, dispatch] = useReducer((s: State, e: Parameters<typeof reducer>[1]) => reducer(s, e), initialState);
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state; // los manejadores de eventos leen siempre el último estado
  }, [state]);
  const agentRef = useRef<AgentClient | null>(null);
  const hostRef = useRef<HostNotifier | null>(null);
  const started = useRef(false);

  const { server } = services;

  const detect = useCallback(async () => {
    const agent = agentRef.current;
    if (!agent) return;
    dispatch({ type: "agent_detecting" });
    try {
      const certificates = await agent.certificates();
      if (certificates.length === 0) dispatch({ type: "agent_problem", code: "token_not_found" });
      else dispatch({ type: "certificates", certificates });
    } catch (error) {
      if (error instanceof AgentUnreachableError) dispatch({ type: "agent_unreachable" });
      else if (error instanceof AgentError) dispatch({ type: "agent_problem", code: error.code });
      else dispatch({ type: "agent_problem", code: "unknown" });
    }
  }, []);

  const complete = useCallback(
    async (signatures: { challenge_id: string; signature_base64: string }[]) => {
      try {
        const context = await server.complete(signatures);
        dispatch({ type: "success", context });
        hostRef.current?.signed(context.document);
      } catch (error) {
        const code = error instanceof ServerError ? error.code : "unknown";
        const status = error instanceof ServerError ? error.status : 0;
        if (status === 409) {
          dispatch({ type: "time_expired" }); // el desafío venció o ya se usó
        } else {
          dispatch({ type: "failed", code: status ? `http_${status}` : code });
          hostRef.current?.failed(code);
        }
      }
    },
    [server],
  );

  const sign = useCallback(
    async (certificate: AgentCertificate, challenges: Challenge[]) => {
      const agent = agentRef.current;
      if (!agent) return;
      dispatch({ type: "awaiting_pin", challenges });
      let signatures;
      try {
        signatures = await agent.sign(certificate.id, challenges);
      } catch (error) {
        if (error instanceof AgentUnreachableError) dispatch({ type: "agent_unreachable" });
        else if (error instanceof AgentError) {
          switch (error.code) {
            case "user_cancelled":
              dispatch({ type: "user_cancelled" });
              break;
            case "pin_incorrect":
            case "pin_expired":
            case "busy":
              dispatch({ type: "pin_error", kind: error.code });
              break;
            case "pin_locked":
              dispatch({ type: "pin_locked" });
              break;
            default:
              dispatch({ type: "agent_problem", code: error.code });
          }
        } else dispatch({ type: "agent_problem", code: "unknown" });
        return;
      }
      dispatch({ type: "completing" });
      await complete(signatures);
    },
    [complete],
  );

  const validate = useCallback(
    async (certificate: AgentCertificate) => {
      try {
        const prepared = await server.prepare(certificate.certificate_pem);
        await sign(certificate, prepared.challenges);
      } catch (error) {
        if (error instanceof ServerError && isCertCode(error.code)) {
          dispatch({ type: "rejected", code: error.code });
        } else {
          const code = error instanceof ServerError ? error.code : "unknown";
          dispatch({ type: "failed", code });
          hostRef.current?.failed(code);
        }
      }
    },
    [server, sign],
  );

  // Arranque: contexto de la solicitud y, para el proveedor token, detección del agente.
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      try {
        const context = await server.getContext();
        hostRef.current = services.createHost(context.allowed_origins, context.id);
        if (context.provider === "token") agentRef.current = services.createAgent(context.agent_url);
        dispatch({ type: "context_loaded", context });
        hostRef.current.ready();
        if (context.provider === "token" && context.status !== "signed") await detect();
      } catch (error) {
        if (error instanceof ServerError && (error.status === 401 || error.code === "invalid_token")) {
          dispatch({ type: "link_invalid" });
        } else {
          dispatch({ type: "failed", code: error instanceof ServerError ? error.code : "unknown" });
        }
      }
    })();
  }, [server, services, detect]);

  const actions: FlowActions = {
    retryDetection: () => void detect(),
    select: (id) => dispatch({ type: "select", id }),
    validateAndContinue: () => {
      const current = stateRef.current;
      if (current.name !== "choose_certificate" || !current.selectedId) return;
      const certificate = current.certificates.find((c) => c.id === current.selectedId);
      if (!certificate) return;
      dispatch({ type: "validating" });
      void validate(certificate);
    },
    retrySign: () => {
      const current = stateRef.current;
      if (current.name === "pin_error") void sign(current.certificate, current.challenges);
    },
    chooseAnother: () => dispatch({ type: "choose_another" }),
    restartSigning: () => {
      const current = stateRef.current;
      if (current.name !== "time_expired") return;
      const { certificate } = current;
      dispatch({ type: "revalidate" });
      void validate(certificate);
    },
    confirmLocal: () => {
      if (stateRef.current.name !== "confirm_local") return;
      dispatch({ type: "local_working" });
      void (async () => {
        try {
          await server.prepare();
          const context = await server.complete([]);
          dispatch({ type: "success", context });
          hostRef.current?.signed(context.document);
        } catch (error) {
          const code = error instanceof ServerError ? error.code : "unknown";
          dispatch({ type: "failed", code });
          hostRef.current?.failed(code);
        }
      })();
    },
    cancel: () => {
      dispatch({ type: "cancelled" });
      hostRef.current?.cancelled();
    },
    close: () => hostRef.current?.closed(),
    download: async () => {
      const { blob, filename } = await server.downloadPdf();
      services.saveFile(blob, filename);
    },
  };

  return { state, actions };
}
