/** Mensajes `postMessage` del widget de firma (ver widget/README.md) traducidos a un resultado para el panel. */

export interface SignResult {
  text: string;
  severity: 'success' | 'error';
}

export type WidgetOutcome = { kind: 'result'; result: SignResult } | { kind: 'closed' } | null;

interface WidgetMessage {
  source?: unknown;
  type?: unknown;
  signed?: unknown;
  total?: unknown;
  code?: unknown;
}

/** Devuelve el resultado que informa el mensaje, `closed` si la persona cerró la pantalla final, o `null` si no es del widget. */
export function parseWidgetMessage(data: unknown): WidgetOutcome {
  if (!data || typeof data !== 'object') return null;
  const message = data as WidgetMessage;
  if (message.source !== 'firmadoc') return null;
  switch (message.type) {
    case 'firmadoc:signed':
      return {
        kind: 'result',
        result: {
          severity: 'success',
          text: 'Documento firmado: quedó como nueva versión vigente. Descargalo desde el módulo de firma.',
        },
      };
    case 'firmadoc:batch-completed': {
      const signed = Number(message.signed) || 0;
      const total = Number(message.total) || 0;
      const all = signed === total;
      return {
        kind: 'result',
        result: {
          severity: all ? 'success' : 'error',
          text: `${signed} de ${total} documentos firmados.` + (all ? '' : ' Podés reintentar los fallidos desde el módulo de firma.'),
        },
      };
    }
    case 'firmadoc:failed':
      return {
        kind: 'result',
        result: { severity: 'error', text: `La firma falló${message.code ? ` (${String(message.code)})` : ''}.` },
      };
    case 'firmadoc:cancelled':
      return {
        kind: 'result',
        result: { severity: 'error', text: 'Firma cancelada. El documento quedó guardado sin firmar.' },
      };
    case 'firmadoc:closed':
      return { kind: 'closed' };
    default:
      return null;
  }
}
