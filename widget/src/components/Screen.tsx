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

/**
 * Pantalla del widget. Sin marco propio (ni marca, ni borde, ni fondo): el widget se ve como parte del diálogo
 * o la página que lo embebe. `tone` queda como clase para quien quiera distinguir error y éxito.
 */
export function Screen({ title, subtitle, announce, children, actions, tone = "default" }: ScreenProps) {
  const heading = useRef<HTMLHeadingElement>(null);
  const announceMessage = useContext(AnnounceContext);

  useEffect(() => {
    heading.current?.focus(); // el foco queda en el título de la pantalla nueva
    announceMessage(announce ?? title);
  }, [announce, announceMessage, title]);

  return (
    <section className={`card card--${tone}`} aria-labelledby="screen-title">
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
