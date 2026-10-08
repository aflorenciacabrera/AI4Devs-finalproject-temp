import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { AGENT_CHECKS } from "../messages/es";

interface Props {
  documentName: string;
  onRetry: () => void;
  onCancel: () => void;
  onChangeProvider?: () => void;
}

export function AgentMissing({ documentName, onRetry, onCancel, onChangeProvider }: Props) {
  return (
    <Screen
      title="No detectamos Firmadoc Agent"
      subtitle={`Firma con token · ${documentName}`}
      tone="error"
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
          <Button onClick={onRetry}>Reintentar detección</Button>
        </>
      }
    >
      <p>Para firmar con tu token, Firmadoc Agent tiene que estar abierto en esta PC.</p>
      <ol className="checks">
        {AGENT_CHECKS.map((check) => (
          <li key={check.title}>
            <strong>{check.title}</strong>
            <span>{check.body}</span>
          </li>
        ))}
      </ol>
      <p className="hint">
        ¿Sigue sin funcionar? Ejecutá el diagnóstico del agente: lista los certificados del token y
        verifica que cargue su biblioteca, sin pedir el PIN.
      </p>
    </Screen>
  );
}
