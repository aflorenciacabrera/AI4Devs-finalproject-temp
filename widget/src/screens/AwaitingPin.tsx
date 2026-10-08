import type { ReactNode } from "react";

import { Screen } from "../components/Screen";

interface Props {
  documentName: string;
  /** `awaiting`: esperando el PIN en el agente. `completing`: firma hecha, se registra en el servidor. */
  phase: "awaiting" | "completing";
}

function Step({ state, children }: { state: "done" | "active" | "todo"; children: ReactNode }) {
  const label = state === "done" ? "Hecho" : state === "active" ? "En curso" : "Pendiente";
  return (
    <li className={`step step--${state}`}>
      <span className="step__mark" aria-hidden="true">
        {state === "done" ? "✓" : state === "active" ? "…" : "·"}
      </span>
      <span className="step__text">{children}</span>
      <span className="sr-only"> ({label})</span>
    </li>
  );
}

export function AwaitingPin({ documentName, phase }: Props) {
  const waiting = phase === "awaiting";
  return (
    <Screen
      title={waiting ? "Esperando tu confirmación" : "Registrando la firma"}
      subtitle={`Firmando · ${documentName}`}
      announce={
        waiting
          ? "Esperando tu confirmación. Ingresá el PIN en la ventana de Firmadoc Agent."
          : "Firma hecha. Registrando la nueva versión del documento."
      }
    >
      {waiting ? (
        <p className="alert alert--info" role="status">
          Ingresá el PIN en la ventana de <strong>Firmadoc Agent</strong> que se abrió en tu PC.
          Firmadoc no recibe tu PIN.
        </p>
      ) : null}
      <ol className="steps">
        <Step state="done">
          Certificado validado
          <small>Cadena de confianza, vigencia, revocación y CUIL</small>
        </Step>
        <Step state={waiting ? "active" : "done"}>
          Esperando el PIN en Firmadoc Agent
          <small>El agente firma solo el hash que preparó el servidor</small>
        </Step>
        <Step state={waiting ? "todo" : "active"}>Incrustar la firma en el documento</Step>
        <Step state="todo">Registrar la nueva versión del documento</Step>
      </ol>
    </Screen>
  );
}
