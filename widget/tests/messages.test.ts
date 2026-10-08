import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  AGENT_CODES,
  CERT_REJECTION_CODES,
  PIN_MESSAGES,
  agentProblem,
  certificateRejection,
  failureMessage,
  providerLabel,
} from "../src/messages/es";

const CONTRACT = resolve(__dirname, "../../docs/agent-contract.md");

/** Códigos de la tabla "Errores del agente" y "Errores que el servidor devuelve" del contrato. */
function codesIn(section: string): string[] {
  const text = readFileSync(CONTRACT, "utf-8");
  const start = text.indexOf(section);
  expect(start, `no se encontró la sección "${section}"`).toBeGreaterThan(-1);
  const rest = text.slice(start + section.length);
  const end = rest.search(/\n##\s/);
  const block = end === -1 ? rest : rest.slice(0, end);
  const codes = new Set<string>();
  for (const line of block.split("\n").filter((l) => l.startsWith("|"))) {
    const cells = line.split("|");
    for (const m of (cells[2] ?? "").matchAll(/`([a-z0-9_]+)`/g)) if (m[1] !== "code") codes.add(m[1]!);
  }
  return [...codes];
}

describe("cobertura de los códigos del contrato", () => {
  it("todos los códigos del agente documentados están contemplados", () => {
    const documented = codesIn("### Errores del agente").filter((c) => c !== "—");
    expect(documented.length).toBeGreaterThan(10);
    for (const code of documented) {
      expect(AGENT_CODES, `falta el código del agente "${code}"`).toContain(code);
    }
  });

  it("todos los códigos de certificado documentados tienen motivo propio", () => {
    const documented = codesIn("## Errores que el servidor devuelve").filter((c) =>
      c.startsWith("certificate_") || c === "cuil_mismatch",
    );
    expect(documented.length).toBeGreaterThanOrEqual(5);
    for (const code of documented) {
      expect(CERT_REJECTION_CODES, code).toContain(code);
    }
  });
});

describe("textos", () => {
  it.each([...CERT_REJECTION_CODES])("el rechazo %s tiene un motivo claro y distinto del genérico", (code) => {
    const generic = certificateRejection("codigo_que_no_existe");
    const own = certificateRejection(code);
    expect(own.reason).not.toBe(generic.reason);
    expect(own.explanation.length).toBeGreaterThan(10);
  });

  it("los códigos de certificado desconocidos caen en el mensaje genérico", () => {
    expect(certificateRejection("xyz").reason).toBe("No se pudo validar el certificado");
  });

  it.each(["token_not_found", "origin_not_allowed", "host_not_allowed", "pkcs11_unavailable"])(
    "el problema del agente %s tiene mensaje propio y una indicación",
    (code) => {
      const generic = agentProblem("otro");
      const message = agentProblem(code);
      expect(message.title).not.toBe(generic.title);
      expect(message.hint).toBeTruthy();
    },
  );

  it.each(AGENT_CODES)("el código del agente %s nunca devuelve un mensaje vacío", (code) => {
    const message = agentProblem(code);
    expect(message.title.length).toBeGreaterThan(5);
    expect(message.body.length).toBeGreaterThan(5);
  });

  it("los errores de PIN nunca sugieren un reintento automático", () => {
    for (const message of Object.values(PIN_MESSAGES)) {
      expect(`${message.title} ${message.body} ${message.hint ?? ""}`).not.toMatch(/reintentando|se reintent/i);
    }
    expect(PIN_MESSAGES["pin_incorrect"]!.body).toMatch(/no reintenta/i);
  });

  it("los fallos desconocidos no muestran el detalle crudo", () => {
    expect(failureMessage("Traceback (most recent call last)").title).toBe("No se pudo completar la firma");
  });

  it("usa el voseo rioplatense de las pantallas del mockup", () => {
    const all = [
      agentProblem("token_not_found").hint,
      certificateRejection("certificate_expired").explanation,
    ].join(" ");
    expect(all).toMatch(/Conectalo|Tenés|renovarlo/);
    expect(all).not.toMatch(/\bConéctalo\b|\bTienes\b/);
  });

  it("etiqueta los proveedores", () => {
    expect(providerLabel("token")).toContain("firma digital");
    expect(providerLabel("local")).toContain("demostración");
  });
});
