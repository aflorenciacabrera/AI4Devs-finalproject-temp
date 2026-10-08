import { useState } from "react";

import { AnnounceContext, Screen } from "./components/Screen";
import { Button, Notice, Spinner } from "./components/Notice";
import {
  INVALID_LINK,
  PIN_LOCKED,
  PIN_MESSAGES,
  TIME_EXPIRED,
  UNSUPPORTED_PROVIDER,
  agentProblem,
  failureMessage,
} from "./messages/es";
import { AgentMissing } from "./screens/AgentMissing";
import { AwaitingPin } from "./screens/AwaitingPin";
import { CertRejected } from "./screens/CertRejected";
import { ChooseCertificate } from "./screens/ChooseCertificate";
import { ConfirmLocal } from "./screens/ConfirmLocal";
import { Success } from "./screens/Success";
import { useSigningFlow, type FlowServices } from "./state/useSigningFlow";

export interface AppProps {
  services: FlowServices;
  now?: () => Date;
}

export function App({ services, now = () => new Date() }: AppProps) {
  const { state, actions } = useSigningFlow(services);
  const [announcement, setAnnouncement] = useState("");

  const screen = (() => {
    switch (state.name) {
      case "loading":
        return (
          <Screen title="Cargando la solicitud de firma">
            <Spinner label="Un momento, por favor…" />
          </Screen>
        );
      case "invalid_link":
        return <Notice message={INVALID_LINK} />;
      case "unsupported":
        return (
          <Notice
            message={UNSUPPORTED_PROVIDER}
            actions={<Button variant="secondary" onClick={actions.cancel}>Cancelar</Button>}
          />
        );
      case "confirm_local":
      case "working_local":
        return (
          <ConfirmLocal
            documentName={state.context.document_name}
            signerName={state.context.signer_name}
            working={state.name === "working_local"}
            onConfirm={actions.confirmLocal}
            onCancel={actions.cancel}
          />
        );
      case "detecting_agent":
        return (
          <Screen title="Buscando Firmadoc Agent">
            <Spinner label="Buscando el agente y el token en esta PC…" />
          </Screen>
        );
      case "agent_missing":
        return (
          <AgentMissing
            documentName={state.context.document_name}
            onRetry={actions.retryDetection}
            onCancel={actions.cancel}
          />
        );
      case "agent_problem":
        return (
          <Notice
            message={agentProblem(state.code)}
            actions={
              <>
                <Button variant="secondary" onClick={actions.cancel}>Cancelar</Button>
                <Button onClick={actions.retryDetection}>Reintentar detección</Button>
              </>
            }
          />
        );
      case "choose_certificate":
        return (
          <ChooseCertificate
            documentName={state.context.document_name}
            certificates={state.certificates}
            selectedId={state.selectedId}
            cancelled={state.notice === "cancelled"}
            now={now()}
            onSelect={actions.select}
            onContinue={actions.validateAndContinue}
            onCancel={actions.cancel}
          />
        );
      case "validating":
        return (
          <Screen title="Validando el certificado">
            <Spinner label="Verificando cadena de confianza, vigencia, revocación y CUIL…" />
          </Screen>
        );
      case "cert_rejected":
        return (
          <CertRejected
            certificate={state.certificate}
            code={state.code}
            onChooseAnother={actions.chooseAnother}
            onCancel={actions.cancel}
          />
        );
      case "awaiting_pin":
      case "completing":
        return (
          <AwaitingPin
            documentName={state.context.document_name}
            phase={state.name === "awaiting_pin" ? "awaiting" : "completing"}
          />
        );
      case "pin_error":
        return (
          <Notice
            message={PIN_MESSAGES[state.kind] ?? PIN_MESSAGES["pin_incorrect"]!}
            actions={
              <>
                <Button variant="secondary" onClick={actions.cancel}>Cancelar</Button>
                {state.kind === "pin_expired" ? null : (
                  <Button onClick={actions.retrySign}>Reintentar</Button>
                )}
              </>
            }
          />
        );
      case "pin_locked":
        return (
          <Notice
            message={PIN_LOCKED}
            actions={<Button variant="secondary" onClick={actions.cancel}>Cerrar</Button>}
          />
        );
      case "time_expired":
        return (
          <Notice
            message={TIME_EXPIRED}
            tone="default"
            actions={
              <>
                <Button variant="secondary" onClick={actions.cancel}>Cancelar</Button>
                <Button onClick={actions.restartSigning}>Volver a empezar</Button>
              </>
            }
          />
        );
      case "success":
        return (
          <Success context={state.context} onDownload={actions.download} onClose={actions.close} />
        );
      case "failed":
        return (
          <Notice
            message={failureMessage(state.code)}
            actions={<Button variant="secondary" onClick={actions.close}>Cerrar</Button>}
          />
        );
      case "cancelled":
        return (
          <Screen title="Firma cancelada">
            <p>No se firmó el documento. Podés cerrar esta ventana y volver al sistema de origen.</p>
          </Screen>
        );
    }
  })();

  return (
    <AnnounceContext.Provider value={setAnnouncement}>
      <main className="shell" key={state.name}>
        {screen}
      </main>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>
    </AnnounceContext.Provider>
  );
}
