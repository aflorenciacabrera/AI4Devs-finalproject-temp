import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";

interface Props {
  documentName: string;
  signerName: string;
  working: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmLocal({ documentName, signerName, working, onConfirm, onCancel }: Props) {
  return (
    <Screen
      title="Firmar el documento"
      subtitle="Firma electrónica de demostración"
      actions={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={working}>
            Cancelar
          </Button>
          <Button onClick={onConfirm} disabled={working}>
            {working ? "Firmando…" : "Firmar"}
          </Button>
        </>
      }
    >
      <dl className="kv">
        <dt>Documento</dt>
        <dd>{documentName}</dd>
        <dt>Firmante</dt>
        <dd>{signerName}</dd>
      </dl>
      <p className="alert alert--info">
        Es una <strong>firma electrónica de demostración</strong> con un certificado propio de
        Firmadoc: sirve para probar el flujo y no equivale a una firma digital con token.
      </p>
    </Screen>
  );
}
