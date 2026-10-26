import type { AgentCertificate } from "../api/types";
import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { commonName, formatDate, parseSubject } from "../format";
import { isExpired } from "../state/machine";

interface Props {
  documentName: string;
  certificates: AgentCertificate[];
  selectedId: string | null;
  cancelled: boolean;
  now: Date;
  onSelect: (id: string) => void;
  onContinue: () => void;
  onCancel: () => void;
  onChangeProvider?: () => void;
}

export function ChooseCertificate({
  documentName,
  certificates,
  selectedId,
  cancelled,
  now,
  onSelect,
  onContinue,
  onCancel,
  onChangeProvider,
}: Props) {
  const selected = certificates.find((c) => c.id === selectedId);
  const canContinue = !!selected && !isExpired(selected, now);
  return (
    <Screen
      title="Elegí el certificado"
      subtitle={`Firma con token · ${documentName}`}
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
          <Button onClick={onContinue} disabled={!canContinue}>
            Validar y continuar
          </Button>
        </>
      }
    >
      <p className="status status--ok">
        <span className="dot" aria-hidden="true" /> Firmadoc Agent conectado · Token criptográfico detectado
      </p>
      {cancelled ? (
        <p className="alert alert--info" role="status">
          Cancelaste la firma en el agente. Podés elegir un certificado y volver a intentarlo.
        </p>
      ) : null}
      <fieldset className="certs">
        <legend className="sr-only">Certificados del token</legend>
        {certificates.map((cert) => {
          const expired = isExpired(cert, now);
          const info = parseSubject(cert.subject);
          const checked = cert.id === selectedId;
          return (
            <label
              key={cert.id}
              className={`cert${checked ? " cert--selected" : ""}${expired ? " cert--expired" : ""}`}
            >
              <input
                type="radio"
                name="certificate"
                value={cert.id}
                checked={checked}
                disabled={expired}
                onChange={() => onSelect(cert.id)}
              />
              <span className="cert__text">
                <strong>{info.name}</strong>
                {info.cuil ? <span>CUIL {info.cuil}</span> : null}
                <span>Emisor: {commonName(cert.issuer)}</span>
                <span className={expired ? "cert__validity cert__validity--bad" : "cert__validity"}>
                  {expired
                    ? `Venció el ${formatDate(cert.not_after)} (no se puede usar)`
                    : `Vigente hasta ${formatDate(cert.not_after)}`}
                </span>
              </span>
            </label>
          );
        })}
      </fieldset>
    </Screen>
  );
}
