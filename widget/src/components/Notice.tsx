import type { ReactNode } from "react";

import type { Message } from "../messages/es";
import { Screen } from "./Screen";

interface NoticeProps {
  message: Message;
  tone?: "default" | "error";
  actions?: ReactNode;
  children?: ReactNode;
  subtitle?: string;
}

/** Pantalla genérica de aviso: título, explicación y, si corresponde, qué hacer a continuación. */
export function Notice({ message, tone = "error", actions, children, subtitle }: NoticeProps) {
  return (
    <Screen title={message.title} tone={tone} actions={actions} subtitle={subtitle}>
      <p>{message.body}</p>
      {message.hint ? <p className="hint">{message.hint}</p> : null}
      {children}
    </Screen>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary";
  disabled?: boolean;
}) {
  return (
    <button type="button" className={`btn btn--${variant}`} onClick={onClick} disabled={disabled}>
      {children}
    </button>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <p className="spinner-row">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </p>
  );
}
