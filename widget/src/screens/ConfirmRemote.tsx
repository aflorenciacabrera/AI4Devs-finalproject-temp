import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { REMOTE_UNAVAILABLE } from "../messages/es";

interface Props {
  documentName: string;
  signerName: string;
  working: boolean;
  unavailable: boolean;
  onConfirm: () => void;
  onChangeProvider?: () => void;
  onCancel: () => void;
}

export function ConfirmRemote({
  documentName,
  signerName,
  working,
  unavailable,
  onConfirm,
  onChangeProvider,
  onCancel,
}: Props) {
  return (
    <Screen
      title="Firmar con el servicio de firma remota"
      subtitle={documentName}
      actions={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={working}>
            Cancelar
          </Button>
          {onChangeProvider ? (
            <Button variant="secondary" onClick={onChangeProvider} disabled={working}>
              Elegir otro método
            </Button>
          ) : null}
          <Button onClick={onConfirm} disabled={working}>
            {working ? "Enviando…" : unavailable ? "Reintentar" : "Continuar"}
          </Button>
        </>
      }
    >
      {unavailable ? (
        <p className="alert alert--error" role="alert">
          <strong>{REMOTE_UNAVAILABLE.title}.</strong> {REMOTE_UNAVAILABLE.hint}
        </p>
      ) : null}
      <dl className="kv">
        <dt>Documento</dt>
        <dd>{documentName}</dd>
        <dt>Firmante</dt>
        <dd>{signerName}</dd>
      </dl>
      <p className="hint">
        Firmadoc enviará el documento al servicio de firma remota. La firma se confirma ahí, con tu
        certificado remoto, un código (OTP) y tu PIN: Firmadoc no los ve.
      </p>
    </Screen>
  );
}
