import { useEffect, useRef, type MouseEvent } from "react";

import { Button, Spinner } from "../components/Notice";
import { Screen } from "../components/Screen";

interface Props {
  documentName: string;
  authorizationUrl: string | null;
  onCancel: () => void;
}

/** Solo se enlaza a http(s): jamás se renderiza un `javascript:` aunque llegue uno. */
export function safeHttpUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export const SERVICE_WINDOW_NAME = "firmadoc-servicio-remoto";
const WIDTH = 520;
const HEIGHT = 680;

/** Lo que el widget necesita de la ventana del servicio (lo que devuelve `window.open`). */
export interface ServiceWindow {
  closed: boolean;
  close(): void;
}

/**
 * Abre el servicio de firma remota en una ventana emergente chica, centrada sobre la del panel, en lugar de otra
 * pestaña. Devuelve `null` si el navegador la bloqueó (entonces el enlace sigue su curso y abre una pestaña).
 * La ventana conserva `opener` para poder cerrarla cuando la firma termine; el iframe del widget está aislado
 * (`sandbox` sin `allow-top-navigation`), así que el servicio no puede navegar la página anfitriona.
 */
export function openServiceWindow(url: string, host: Window = window): ServiceWindow | null {
  const left = Math.max(0, Math.round(host.screenX + (host.outerWidth - WIDTH) / 2));
  const top = Math.max(0, Math.round(host.screenY + (host.outerHeight - HEIGHT) / 2));
  const features = `popup=yes,width=${WIDTH},height=${HEIGHT},left=${left},top=${top},resizable=yes,scrollbars=yes`;
  try {
    return host.open(url, SERVICE_WINDOW_NAME, features);
  } catch {
    return null;
  }
}

export function RemoteWaiting({ documentName, authorizationUrl, onCancel }: Props) {
  const href = safeHttpUrl(authorizationUrl);
  const service = useRef<ServiceWindow | null>(null);

  // Al salir de la espera (firmado, rechazado, vencido o cancelado) la ventana del servicio ya no hace falta.
  useEffect(
    () => () => {
      if (service.current && !service.current.closed) service.current.close();
      service.current = null;
    },
    [],
  );

  const open = (event: MouseEvent<HTMLAnchorElement>) => {
    if (service.current && !service.current.closed) {
      event.preventDefault();
      service.current.close(); // una sola ventana: la nueva reemplaza a la anterior
    }
    const opened = openServiceWindow(event.currentTarget.href);
    if (!opened) return; // bloqueada: el enlace abre una pestaña, como antes
    service.current = opened;
    event.preventDefault();
  };

  return (
    <Screen
      title="Esperando la firma en el servicio remoto"
      subtitle={documentName}
      announce="Esperando que confirmes la firma en el servicio de firma remota."
      actions={
        <Button variant="secondary" onClick={onCancel}>
          Cancelar
        </Button>
      }
    >
      {href ? (
        <p>
          <a className="btn btn--primary" href={href} target="_blank" rel="noreferrer" onClick={open}>
            Continuar en el servicio de firma
          </a>
        </p>
      ) : (
        <p className="hint">Ya iniciaste la firma. Retomala desde la ventana del servicio de firma remota.</p>
      )}
      <Spinner label="Esperando la confirmación del servicio…" />
    </Screen>
  );
}
