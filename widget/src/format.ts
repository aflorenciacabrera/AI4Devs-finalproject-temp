/** Formato de datos de certificados y fechas para mostrar a la persona. */

export interface SubjectInfo {
  name: string;
  cuil: string | null;
}

const CUIL = /CUIL\s*(\d{2})-?(\d{8})-?(\d)/i;

export function formatCuil(raw: string): string {
  const m = CUIL.exec(`CUIL ${raw}`);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : raw;
}

/** Nombre (CN) y CUIL de un sujeto en formato RFC 4514 (`CN=Juan,2.5.4.5=CUIL 20111111112,C=AR`). */
export function parseSubject(subject: string): SubjectInfo {
  const cn = /(?:^|,)\s*CN=([^,]+)/i.exec(subject)?.[1]?.trim();
  const cuil = CUIL.exec(subject);
  return {
    name: cn ?? subject,
    cuil: cuil ? `${cuil[1]}-${cuil[2]}-${cuil[3]}` : null,
  };
}

export const commonName = (dn: string): string => parseSubject(dn).name;

export function formatDate(iso: string, locale = "es-AR"): string {
  return new Date(iso).toLocaleDateString(locale, { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function formatDateTime(iso: string, locale = "es-AR"): string {
  return new Date(iso).toLocaleString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
