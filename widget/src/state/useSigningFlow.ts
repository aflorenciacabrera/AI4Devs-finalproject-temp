/**
 * Orquesta el flujo: servidor (contexto, prepare, complete) y agente (certificados, firma).
 * Toda la lógica de decisión está en `machine.ts`; acá solo están los efectos.
 */

import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import { AgentError, AgentUnreachableError, ServerError } from "../api/errors";
import type { AgentClient } from "../api/agentClient";
import type { ServerClient } from "../api/serverClient";
import type { AgentCertificate, Challenge } from "../api/types";
import { CERT_REJECTION_CODES } from "../messages/es";
import type { HostNotifier } from "../embed/hostMessages";
import type { WidgetContext } from "../api/types";
import { initialRoute, initialState, reducer, routeAfterChoice, type State } from "./machine";

export interface FlowServices {
  server: ServerClient;
  /** Se crea cuando se conoce la URL del agente (la informa el servidor en el contexto). */
  createAgent: (agentUrl: string) => AgentClient;
  /** Crea el notificador cuando se conocen los orígenes permitidos. */
  createHost: (allowedOrigins: string[], requestId: string) => HostNotifier;
  saveFile: (blob: Blob, filename: string) => void;
  /** Pasa a otra página de firma (el reintento de un lote abre el lote nuevo). */
  navigate?: (url: string) => void;
  /** Cada cuánto se consulta el estado mientras se espera la firma remota (ms). */
  pollMs?: number;
}

export interface FlowActions {
  retryDetection(): void;
  select(id: string): void;
  validateAndContinue(): void;
  retrySign(): void;
  chooseAnother(): void;
  restartSigning(): void;
  confirmLocal(): void;
  chooseProvider(provider: string): void;
  changeProvider(): void;
  confirmRemote(): void;
  cancel(): void;
  close(): void;
  download(): Promise<void>;
  /** Solo en lotes: crea otro lote con los documentos fallidos y lo abre. */
  retryFailed(): Promise<void>;
}

/** Cómo está el agente local, para la pantalla de elección del método. */
export type AgentStatus = "unknown" | "checking" | "connected" | "no_token" | "missing";

const isCertCode = (code: string) => (CERT_REJECTION_CODES as readonly string[]).includes(code);

export function useSigningFlow(services: FlowServices): {
  state: State;
  actions: FlowActions;
  agentStatus: AgentStatus;
} {
  const [state, dispatch] = useReducer((s: State, e: Parameters<typeof reducer>[1]) => reducer(s, e), initialState);
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state; // los manejadores de eventos leen siempre el último estado
  }, [state]);
  const agentRef = useRef<AgentClient | null>(null);
  const hostRef = useRef<HostNotifier | null>(null);
  const started = useRef(false);
  const [agentResult, setAgentResult] = useState<{ url: string; status: AgentStatus } | null>(null);

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

  const notifySuccess = useCallback((context: WidgetContext) => {
    if (context.batch) hostRef.current?.batchCompleted(context.batch, context.id);
    else hostRef.current?.signed(context.document);
  }, []);

  const complete = useCallback(
    async (signatures: { challenge_id: string; signature_base64: string }[]) => {
      try {
        const context = await server.complete(signatures);
        dispatch({ type: "success", context });
        notifySuccess(context);
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
    [server, notifySuccess],
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
        const detectsAgent = initialRoute(context).name === "detecting_agent";
        if (detectsAgent) agentRef.current = services.createAgent(context.agent_url);
        dispatch({ type: "context_loaded", context });
        hostRef.current.ready();
        if (detectsAgent) await detect();
      } catch (error) {
        if (error instanceof ServerError && (error.status === 401 || error.code === "invalid_token")) {
          dispatch({ type: "link_invalid" });
        } else {
          dispatch({ type: "failed", code: error instanceof ServerError ? error.code : "unknown" });
        }
      }
    })();
  }, [server, services, detect]);

  // Elección del método: si el token es una opción, se consulta al agente para mostrar si está conectado.
  const choosing = state.name === "choose_provider" ? state.context : null;
  const offersToken = choosing?.allowed_providers.includes("token") ?? false;
  const agentUrl = choosing?.agent_url ?? null;
  useEffect(() => {
    if (!offersToken || !agentUrl) return;
    let stopped = false;
    services
      .createAgent(agentUrl)
      .certificates()
      .then((certs) => !stopped && setAgentResult({ url: agentUrl, status: certs.length > 0 ? "connected" : "no_token" }))
      .catch((error: unknown) => {
        if (stopped) return;
        setAgentResult({ url: agentUrl, status: error instanceof AgentError ? "no_token" : "missing" });
      });
    return () => {
      stopped = true;
    };
  }, [offersToken, agentUrl, services]);

  const agentStatus: AgentStatus = !offersToken
    ? "unknown"
    : agentResult && agentResult.url === agentUrl
      ? agentResult.status
      : "checking";

  // Firma remota: se consulta el estado hasta que el callback del servicio resuelva la solicitud.
  const pollMs = services.pollMs ?? 3000;
  useEffect(() => {
    if (state.name !== "remote_waiting") return;
    let stopped = false;
    let busy = false;
    const timer = setInterval(() => {
      if (busy || stopped) return;
      busy = true;
      server
        .getContext()
        .then((context) => {
          if (stopped) return;
          if (context.status === "signed") {
            stopped = true; // un segundo ciclo no debe avisar de nuevo mientras React desmonta el efecto
            dispatch({ type: "success", context });
            notifySuccess(context);
          } else if (context.status === "failed") {
            stopped = true;
            dispatch({ type: "failed", code: "request_failed" });
            hostRef.current?.failed("request_failed");
          }
        })
        .catch(() => undefined) // fallo transitorio: se reintenta en el próximo ciclo
        .finally(() => {
          busy = false;
        });
    }, pollMs);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [state.name, server, pollMs, notifySuccess]);

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
          notifySuccess(context);
        } catch (error) {
          const code = error instanceof ServerError ? error.code : "unknown";
          dispatch({ type: "failed", code });
          hostRef.current?.failed(code);
        }
      })();
    },
    chooseProvider: (provider) => {
      const current = stateRef.current;
      if (current.name !== "choose_provider" || current.pending) return;
      dispatch({ type: "choosing", provider });
      void (async () => {
        try {
          const context = await server.selectProvider(provider);
          const next = routeAfterChoice(context);
          if (next.name === "detecting_agent") agentRef.current = services.createAgent(context.agent_url);
          dispatch({ type: "provider_selected", context });
          if (next.name === "detecting_agent") await detect();
        } catch (error) {
          dispatch({ type: "choose_failed", code: error instanceof ServerError ? error.code : "unknown" });
        }
      })();
    },
    changeProvider: () => dispatch({ type: "change_provider" }),
    confirmRemote: () => {
      const current = stateRef.current;
      if (current.name !== "confirm_remote" || current.working) return;
      dispatch({ type: "remote_starting" });
      void (async () => {
        try {
          const prepared = await server.prepare();
          if (!prepared.remote) throw new ServerError("invalid_response", 200, "falta la operación remota");
          dispatch({ type: "remote_started", authorizationUrl: prepared.remote.authorization_url });
        } catch (error) {
          if (error instanceof ServerError && error.status === 503) {
            dispatch({ type: "remote_failed", code: "remote_unavailable" });
          } else {
            const code = error instanceof ServerError ? error.code : "unknown";
            dispatch({ type: "failed", code });
            hostRef.current?.failed(code);
          }
        }
      })();
    },
    cancel: () => {
      dispatch({ type: "cancelled" });
      hostRef.current?.cancelled();
    },
    close: () => hostRef.current?.closed(),
    retryFailed: async () => {
      if (!server.retry) return;
      const { signing_url } = await server.retry();
      (services.navigate ?? ((url: string) => window.location.assign(url)))(signing_url);
    },
    download: async () => {
      const { blob, filename } = await server.downloadPdf();
      services.saveFile(blob, filename);
    },
  };

  return { state, actions, agentStatus };
}
