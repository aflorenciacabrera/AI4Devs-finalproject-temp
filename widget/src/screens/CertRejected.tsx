import type { AgentCertificate } from "../api/types";
import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { parseSubject } from "../format";
import { certificateRejection } from "../messages/es";

interface Props {
  certificate: AgentCertificate;
  code: string;
  onChooseAnother: () => void;
  onCancel: () => void;
  onChangeProvider?: () => void;
}

export function CertRejected({ certificate, code, onChooseAnother, onCancel, onChangeProvider }: Props) {
  const { reason, explanation } = certificateRejection(code);
  const info = parseSubject(certificate.subject);
  return (
    <Screen
      title="El certificado no pudo validarse"
      tone="error"
      announce={`El certificado no pudo validarse. Motivo: ${reason}. No se te pidió el PIN.`}
      actions={
        <>
          <Button variant="secondary" onClick={onCancel}>
            Cancelar
          </Button>
          {onChangeProvider ? (
            <Button variant="secondary" onClick={onChangeProvider}>
              Elegir otro método
            </Button>
          ) : null}
          <Button onClick={onChooseAnother}>Elegir otro certificado</Button>
        </>
      }
    >
      <p className="alert alert--error">
        <strong>No se te pidió el PIN:</strong> Firmadoc rechazó el certificado antes de iniciar la firma.
      </p>
      <dl className="kv">
        <dt>Certificado</dt>
        <dd>{info.name}</dd>
        <dt>Serie</dt>
        <dd className="mono">{certificate.serial_number}</dd>
        <dt>Motivo</dt>
        <dd>
          <strong className="reason">{reason}</strong>
          <span className="reason__text">{explanation}</span>
        </dd>
      </dl>
    </Screen>
  );
}
