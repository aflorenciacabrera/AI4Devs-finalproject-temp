/**
 * Todos los textos de error en un solo lugar (español rioplatense). Cada código estable del servidor y
 * del agente tiene su mensaje; los desconocidos caen en uno genérico, nunca se muestra el detalle crudo.
 */

export interface Message {
  title: string;
  body: string;
  hint?: string;
}

/** Códigos con los que el servidor rechaza un certificado en `prepare` (docs/agent-contract.md). */
export const CERT_REJECTION_CODES = [
  "certificate_revoked",
  "certificate_expired",
  "certificate_untrusted",
  "certificate_invalid",
  "cuil_mismatch",
] as const;

/** Códigos de error del agente (docs/agent-contract.md). */
export const AGENT_CODES = [
  "invalid_request",
  "origin_not_allowed",
  "host_not_allowed",
  "not_found",
  "token_not_found",
  "certificate_not_found",
  "private_key_not_found",
  "method_not_allowed",
  "user_cancelled",
  "pin_incorrect",
  "pin_expired",
  "pin_locked",
  "busy",
  "pkcs11_unavailable",
  "pkcs11_error",
] as const;

const REJECTION_REASONS: Record<string, { reason: string; explanation: string }> = {
  certificate_revoked: {
    reason: "Certificado revocado",
    explanation: "La autoridad certificante lo dio de baja. Pedí uno nuevo a tu área de sistemas.",
  },
  certificate_expired: {
    reason: "Certificado vencido",
    explanation: "Ya pasó su fecha de vigencia. Tenés que renovarlo.",
  },
  certificate_untrusted: {
    reason: "Autoridad certificante no confiable",
    explanation: "Lo emitió una autoridad que Firmadoc no reconoce.",
  },
  certificate_invalid: {
    reason: "Certificado no válido",
    explanation: "No sirve para firmar documentos o no se pudo verificar.",
  },
  cuil_mismatch: {
    reason: "CUIL distinto al del firmante",
    explanation: "Este certificado no corresponde a la persona que debe firmar este documento.",
  },
};

export function certificateRejection(code: string): { reason: string; explanation: string } {
  return (
    REJECTION_REASONS[code] ?? {
      reason: "No se pudo validar el certificado",
      explanation: "Firmadoc no pudo aceptar este certificado. Probá con otro o consultá a tu área de sistemas.",
    }
  );
}

const AGENT_PROBLEMS: Record<string, Message> = {
  token_not_found: {
    title: "No encontramos el token",
    body: "Firmadoc Agent está funcionando, pero no detecta ningún token conectado.",
    hint: "Conectalo a un puerto USB y reintentá.",
  },
  origin_not_allowed: {
    title: "Este sitio no está autorizado en tu agente",
    body: "El Firmadoc Agent de esta PC no acepta pedidos de este sitio.",
    hint: "Pedile a tu área de sistemas que agregue este sitio a los orígenes permitidos del agente.",
  },
  host_not_allowed: {
    title: "El agente rechazó la conexión",
    body: "El agente no aceptó la dirección desde la que se lo consultó.",
    hint: "Consultá a tu área de sistemas.",
  },
  pkcs11_unavailable: {
    title: "No se puede usar el software del token",
    body: "El software del fabricante del token no está instalado o no se pudo cargar.",
    hint: "Ejecutá el diagnóstico del agente: lista los certificados del token y verifica su biblioteca, sin pedir el PIN.",
  },
};

const GENERIC_AGENT: Message = {
  title: "El agente no pudo completar la operación",
  body: "Firmadoc Agent respondió con un error inesperado.",
  hint: "Reintentá. Si sigue igual, ejecutá el diagnóstico del agente o consultá a tu área de sistemas.",
};

export function agentProblem(code: string): Message {
  return AGENT_PROBLEMS[code] ?? GENERIC_AGENT;
}

export const AGENT_CHECKS = [
  {
    title: "Firmadoc Agent instalado y en ejecución",
    body: "No respondió en esta PC. Abrilo, o pedí su instalación a tu área de sistemas.",
  },
  {
    title: "Token conectado, con el software del fabricante instalado",
    body: "Conectalo a un puerto USB antes de reintentar.",
  },
  {
    title: "Este sitio autorizado en el agente",
    body: "El agente solo acepta pedidos de los sitios que su configuración permite. Si está abierto y igual no responde, pedile a tu área de sistemas que autorice este sitio.",
  },
  {
    title: "Permiso de acceso a la red local",
    body: "Si el navegador pregunta si este sitio puede conectarse a dispositivos de tu red local, elegí Permitir.",
  },
] as const;

export const PIN_MESSAGES: Record<string, Message> = {
  pin_incorrect: {
    title: "PIN incorrecto",
    body: "El token no aceptó el PIN. Firmadoc no reintenta por su cuenta: cada intento fallido cuenta para el bloqueo del token.",
    hint: "Cuando estés listo, reintentá e ingresá el PIN con cuidado.",
  },
  pin_expired: {
    title: "El PIN del token venció",
    body: "El token pide cambiar el PIN antes de seguir.",
    hint: "Cambialo con el software del fabricante del token y volvé a intentar.",
  },
  busy: {
    title: "Ya hay una firma esperando confirmación",
    body: "Firmadoc Agent tiene otra ventana de firma abierta en esta PC.",
    hint: "Terminá o cancelá esa ventana y reintentá.",
  },
};

export const PIN_LOCKED: Message = {
  title: "El token está bloqueado",
  body: "Se superó la cantidad de intentos de PIN permitidos.",
  hint: "El token se desbloquea con el administrador del token (con el PUK). Firmadoc no puede hacerlo.",
};

const FAILURES: Record<string, Message> = {
  request_failed: {
    title: "La firma no se completó",
    body: "El servicio de firma remota informó que la firma fue rechazada o venció.",
    hint: "Volvé al sistema de origen y pedí firmar el documento de nuevo.",
  },
  network_error: {
    title: "No pudimos comunicarnos con Firmadoc",
    body: "Se perdió la conexión con el servidor.",
    hint: "Revisá tu conexión y reintentá desde el sistema de origen.",
  },
  invalid_response: {
    title: "Respuesta inesperada",
    body: "El servidor respondió algo que Firmadoc no entiende.",
    hint: "Reintentá. Si sigue igual, avisá a tu área de sistemas.",
  },
  http_409: {
    title: "La firma no se puede continuar",
    body: "La solicitud cambió de estado mientras firmabas.",
    hint: "Volvé al sistema de origen y revisá el estado del documento.",
  },
  http_422: {
    title: "No se pudo completar la firma",
    body: "El servidor rechazó la firma: no corresponde al documento preparado.",
    hint: "Volvé a intentarlo desde el sistema de origen.",
  },
};

const GENERIC_FAILURE: Message = {
  title: "No se pudo completar la firma",
  body: "Ocurrió un error inesperado.",
  hint: "Reintentá desde el sistema de origen. Si sigue igual, avisá a tu área de sistemas.",
};

export function failureMessage(code: string): Message {
  return FAILURES[code] ?? GENERIC_FAILURE;
}

export const INVALID_LINK: Message = {
  title: "El enlace de firma no es válido o venció",
  body: "No podemos continuar con esta firma.",
  hint: "Volvé al sistema de origen y pedí firmar el documento de nuevo.",
};

export const UNSUPPORTED_PROVIDER: Message = {
  title: "Este método de firma no está disponible",
  body: "El método de firma de esta solicitud todavía no se puede usar desde Firmadoc.",
  hint: "Volvé al sistema de origen y consultá con tu área de sistemas.",
};

export const TIME_EXPIRED: Message = {
  title: "Se agotó el tiempo para firmar",
  body: "Por seguridad, la preparación de la firma vence a los pocos minutos y ya no sirve.",
  hint: "Volvé a empezar: se vuelve a validar el mismo certificado.",
};

export const providerLabel = (provider: string): string =>
  provider === "token"
    ? "Token · firma digital"
    : provider === "local"
      ? "Firma electrónica de demostración"
      : provider === "firmar"
        ? "Servicio de firma remota"
        : provider;

export interface ProviderChoice {
  title: string;
  badge: string;
  description: string;
  /** Texto de la tarjeta cuando se firma un lote (`{n}` = cantidad de documentos). */
  batchDescription?: string;
}

export const PROVIDER_CHOICES: Record<string, ProviderChoice> = {
  token: {
    title: "Firma con token",
    badge: "Firma digital",
    description:
      "Firmás con el token USB conectado a tu PC. El PIN se ingresa solo en tu PC y la clave nunca sale del token.",
    batchDescription:
      "El PIN se pide una sola vez para los {n} documentos. Se firman todos juntos y la clave nunca sale del token.",
  },
  local: {
    title: "Firma propia",
    badge: "Demostración",
    description:
      "Certificado de demostración, sin token. Es firma electrónica: no tiene la presunción legal de la firma digital (Ley 25.506).",
  },
  firmar: {
    title: "Firma remota",
    badge: "Firmar",
    description:
      "Te redirigimos al servicio de firma remota para que confirmes con tu certificado remoto. Firmadoc no accede a tu credencial.",
    batchDescription:
      "Confirmás con tu certificado remoto en el servicio externo. Puede limitar la cantidad de documentos por lote.",
  },
};

export const REMOTE_NOT_FOR_BATCHES = "No está disponible para firmar lotes.";

export const AGENT_STATUS_TEXT: Record<string, string> = {
  checking: "Buscando Firmadoc Agent…",
  connected: "Firmadoc Agent conectado · token detectado",
  no_token: "Firmadoc Agent conectado · no se detectó el token",
  missing: "No detectamos Firmadoc Agent en esta PC",
};

export const CHOOSE_FAILED: Message = {
  title: "No se pudo elegir ese método",
  body: "Firmadoc no aceptó el método elegido para esta solicitud.",
  hint: "Probá con otro método o volvé al sistema de origen.",
};

export const REMOTE_UNAVAILABLE: Message = {
  title: "El servicio de firma remota no está disponible",
  body: "Firmadoc no pudo comunicarse con el servicio para iniciar la firma.",
  hint: "Reintentá en unos minutos o elegí otro método.",
};
