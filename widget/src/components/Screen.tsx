import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";

/** Región `aria-live` persistente: un cambio de pantalla se anuncia aunque la pantalla se desmonte. */
export const AnnounceContext = createContext<(message: string) => void>(() => {});

interface ScreenProps {
  title: string;
  subtitle?: string;
  /** Texto que se anuncia a lectores de pantalla; por defecto, el título. */
  announce?: string;
  children?: ReactNode;
  actions?: ReactNode;
  tone?: "default" | "error" | "success";
}

/** En un iframe el widget es un módulo de otra pantalla; en una ventana propia, es la pantalla. */
const FRAMED = typeof window !== "undefined" && window.parent !== window;

export function Screen({ title, subtitle, announce, children, actions, tone = "default" }: ScreenProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const announceMessage = useContext(AnnounceContext);

  useEffect(() => {
    heading.current?.focus(); // el foco queda en el título de la pantalla nueva
    announceMessage(announce ?? title);
  }, [announce, announceMessage, title]);

  return (
    <section className={`card card--${tone}`} aria-labelledby="screen-title">
      <header className="brandbar">
        <span className="brand">Firmadoc</span>
        <span className="chip">{FRAMED ? "Módulo embebido" : "Ventana de firma"}</span>
      </header>
      <div className="body">
        <h1 id="screen-title" tabIndex={-1} ref={heading}>
          {title}
        </h1>
        {subtitle ? <p className="subtitle">{subtitle}</p> : null}
        {children}
      </div>
      {actions ? <footer className="actions">{actions}</footer> : null}
    </section>
  );
}
