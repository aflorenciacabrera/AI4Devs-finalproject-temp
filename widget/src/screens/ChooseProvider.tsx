import { Button } from "../components/Notice";
import { Screen } from "../components/Screen";
import { CHOOSE_FAILED, PROVIDER_CHOICES } from "../messages/es";

interface Props {
  documentName: string;
  providers: string[];
  pending: string | null;
  failed: boolean;
  onChoose: (provider: string) => void;
  onCancel: () => void;
}

export function ChooseProvider({ documentName, providers, pending, failed, onChoose, onCancel }: Props) {
  return (
    <Screen
      title="¿Cómo querés firmar?"
      subtitle={documentName}
      actions={
        <Button variant="secondary" onClick={onCancel} disabled={pending !== null}>
          Cancelar
        </Button>
      }
    >
      {failed ? (
        <p className="alert alert--error" role="alert">
          <strong>{CHOOSE_FAILED.title}.</strong> {CHOOSE_FAILED.hint}
        </p>
      ) : null}
      <ul className="choices">
        {providers.map((provider) => {
          const info = PROVIDER_CHOICES[provider] ?? { title: provider, description: "" };
          return (
            <li key={provider}>
              <button
                type="button"
                className="choice"
                onClick={() => onChoose(provider)}
                disabled={pending !== null}
                aria-busy={pending === provider}
              >
                <strong>{info.title}</strong>
                <span>{info.description}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </Screen>
  );
}
