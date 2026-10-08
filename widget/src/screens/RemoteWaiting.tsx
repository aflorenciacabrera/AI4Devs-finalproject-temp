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

export function RemoteWaiting({ documentName, authorizationUrl, onCancel }: Props) {
  const href = safeHttpUrl(authorizationUrl);
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
          <a className="btn btn--primary" href={href} target="_blank" rel="noopener noreferrer">
            Continuar en el servicio de firma
          </a>
        </p>
      ) : (
        <p className="hint">
          Ya iniciaste la firma. Retomala desde la pestaña del servicio de firma remota.
        </p>
      )}
      <Spinner label="Esperando la confirmación del servicio…" />
      <p className="hint">Esta pantalla se actualiza sola cuando el servicio informa el resultado.</p>
    </Screen>
  );
}
