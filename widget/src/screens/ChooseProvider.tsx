import { useState } from "react";

import type { WidgetContext } from "../api/types";
import { BatchDocumentList, DocumentCard } from "../components/DocumentCard";
import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import type { AgentStatus } from "../state/useSigningFlow";
import {
  AGENT_STATUS_TEXT,
  CHOOSE_FAILED,
  PROVIDER_CHOICES,
  REMOTE_NOT_FOR_BATCHES,
} from "../messages/es";

interface Props {
  context: WidgetContext;
  agentStatus: AgentStatus;
  pending: string | null;
  failed: boolean;
  onChoose: (provider: string) => void;
  onCancel: () => void;
}

export function ChooseProvider({ context, agentStatus, pending, failed, onChoose, onCancel }: Props) {
  const documents = context.batch?.documents;
  const count = documents?.length ?? 1;
  // En un lote la firma remota se muestra, pero deshabilitada: el servidor no la admite por lote.
  const providers = documents && !context.allowed_providers.includes("firmar")
    ? [...context.allowed_providers, "firmar"]
    : context.allowed_providers;
  const enabled = (provider: string) => !(documents && provider === "firmar");

  const [picked, setPicked] = useState<string | null>(null);
  const preferred =
    context.allowed_providers.includes("token") && agentStatus === "connected"
      ? "token"
      : context.allowed_providers.includes(context.provider)
        ? context.provider
        : (context.allowed_providers[0] ?? "");
  const selected = picked && enabled(picked) ? picked : preferred;
  const busy = pending !== null;

  return (
    <Screen
      title="Elegí el método de firma"
      subtitle={documents ? `Firma en lote · ${count} documentos` : undefined}
      actions={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Cancelar
          </Button>
          <Button onClick={() => onChoose(selected)} disabled={busy || !selected}>
            {busy ? "Preparando…" : documents ? `Firmar ${count} documentos` : "Firmar documento"}
          </Button>
        </>
      }
    >
      {documents ? <BatchDocumentList documents={documents} /> : <DocumentCard context={context} />}
      {failed ? (
        <p className="alert alert--error" role="alert">
          <strong>{CHOOSE_FAILED.title}.</strong> {CHOOSE_FAILED.hint}
        </p>
      ) : null}
      <div className="choices" role="radiogroup" aria-label="Método de firma">
        {providers.map((provider) => {
          const info = PROVIDER_CHOICES[provider] ?? { title: provider, badge: "", description: "" };
          const isEnabled = enabled(provider);
          const description = (documents && info.batchDescription ? info.batchDescription : info.description).replace(
            "{n}",
            String(count),
          );
          return (
            <label
              key={provider}
              className={`choice-card${selected === provider ? " choice-card--selected" : ""}${isEnabled ? "" : " choice-card--disabled"}`}
            >
              <input
                type="radio"
                name="provider"
                value={provider}
                checked={selected === provider}
                disabled={busy || !isEnabled}
                onChange={() => setPicked(provider)}
              />
              <span className="choice-card__head">
                <strong>{info.title}</strong>
                {info.badge ? <span className="badge">{info.badge}</span> : null}
              </span>
              <span className="choice-card__text">{description}</span>
              {provider === "token" ? (
                <span className={`agent-status agent-status--${agentStatus}`} role="status">
                  {AGENT_STATUS_TEXT[agentStatus] ?? ""}
                </span>
              ) : null}
              {!isEnabled ? <span className="choice-card__note">{REMOTE_NOT_FOR_BATCHES}</span> : null}
            </label>
          );
        })}
      </div>
    </Screen>
  );
}
