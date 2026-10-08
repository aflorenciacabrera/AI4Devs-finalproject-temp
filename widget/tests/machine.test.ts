import { describe, expect, it } from "vitest";

import { initialState, isCancellable, isExpired, reducer, type Event, type State } from "../src/state/machine";
import { challenge, makeCert, makeContext, signedContext } from "./fixtures";

const NOW = new Date("2026-10-08T12:00:00Z");
const ctx = makeContext();
const cert = makeCert();
const expiredCert = makeCert({ id: "SERIE1:02", not_after: "2025-05-05T00:00:00+00:00" });

function run(start: State, ...events: Event[]): State {
  return events.reduce((s, e) => reducer(s, e, NOW), start);
}

const choosing = run(initialState, { type: "context_loaded", context: ctx }, {
  type: "certificates",
  certificates: [expiredCert, cert],
});

describe("arranque", () => {
  it("proveedor token → detectando el agente", () => {
    expect(run(initialState, { type: "context_loaded", context: ctx }).name).toBe("detecting_agent");
  });
  it("proveedor local → confirmación", () => {
    expect(run(initialState, { type: "context_loaded", context: makeContext({ provider: "local" }) }).name).toBe(
      "confirm_local",
    );
  });
  it("proveedor firmar → no soportado", () => {
    expect(run(initialState, { type: "context_loaded", context: makeContext({ provider: "firmar" }) }).name).toBe(
      "unsupported",
    );
  });
  it("solicitud ya firmada → muestra la firma completada", () => {
    expect(run(initialState, { type: "context_loaded", context: signedContext() }).name).toBe("success");
  });
  it("solicitud fallida → error", () => {
    expect(run(initialState, { type: "context_loaded", context: makeContext({ status: "failed" }) }).name).toBe("failed");
  });
  it("enlace inválido", () => {
    expect(run(initialState, { type: "link_invalid" }).name).toBe("invalid_link");
  });
});

describe("agente y certificados", () => {
  it("agente ausente y problemas del agente", () => {
    const detecting = run(initialState, { type: "context_loaded", context: ctx });
    expect(run(detecting, { type: "agent_unreachable" }).name).toBe("agent_missing");
    expect(run(detecting, { type: "agent_problem", code: "token_not_found" })).toMatchObject({
      name: "agent_problem",
      code: "token_not_found",
    });
  });

  it("reintentar la detección vuelve a 'detectando'", () => {
    const missing = run(initialState, { type: "context_loaded", context: ctx }, { type: "agent_unreachable" });
    expect(run(missing, { type: "agent_detecting" }).name).toBe("detecting_agent");
  });

  it("preselecciona el primer certificado vigente (no el vencido)", () => {
    expect(choosing).toMatchObject({ name: "choose_certificate", selectedId: cert.id });
  });

  it("sin certificados vigentes no preselecciona nada", () => {
    const s = run(initialState, { type: "context_loaded", context: ctx }, { type: "certificates", certificates: [expiredCert] });
    expect(s).toMatchObject({ selectedId: null });
    expect(run(s, { type: "validating" }).name).toBe("choose_certificate"); // no se puede validar sin selección
  });

  it("isExpired", () => {
    expect(isExpired(expiredCert, NOW)).toBe(true);
    expect(isExpired(cert, NOW)).toBe(false);
  });

  it("seleccionar solo funciona al elegir", () => {
    expect(run(choosing, { type: "select", id: expiredCert.id })).toMatchObject({ selectedId: expiredCert.id });
    expect(run(initialState, { type: "select", id: "x" })).toEqual(initialState);
  });
});

describe("validación y firma", () => {
  const validating = run(choosing, { type: "validating" });

  it("validar toma el certificado seleccionado", () => {
    expect(validating).toMatchObject({ name: "validating", certificate: { id: cert.id } });
  });

  it("rechazado → pantalla con el motivo; elegir otro vuelve a la lista sin el rechazado", () => {
    const rejected = run(validating, { type: "rejected", code: "certificate_revoked" });
    expect(rejected).toMatchObject({ name: "cert_rejected", code: "certificate_revoked" });
    const again = run(rejected, { type: "choose_another" });
    expect(again.name).toBe("choose_certificate");
    expect(again).toMatchObject({ selectedId: null }); // el único vigente era el rechazado
  });

  it("firma completa", () => {
    const awaiting = run(validating, { type: "awaiting_pin", challenges: [challenge] });
    expect(awaiting.name).toBe("awaiting_pin");
    const completing = run(awaiting, { type: "completing" });
    expect(completing.name).toBe("completing");
    expect(run(completing, { type: "success", context: signedContext() }).name).toBe("success");
  });

  it("PIN incorrecto permite reintentar con los mismos desafíos (sin volver a preparar)", () => {
    const awaiting = run(validating, { type: "awaiting_pin", challenges: [challenge] });
    const error = run(awaiting, { type: "pin_error", kind: "pin_incorrect" });
    expect(error).toMatchObject({ name: "pin_error", kind: "pin_incorrect", challenges: [challenge] });
    expect(run(error, { type: "awaiting_pin", challenges: [challenge] }).name).toBe("awaiting_pin");
  });

  it("cancelar en el agente vuelve a elegir el mismo certificado, con aviso", () => {
    const awaiting = run(validating, { type: "awaiting_pin", challenges: [challenge] });
    expect(run(awaiting, { type: "user_cancelled" })).toMatchObject({
      name: "choose_certificate",
      selectedId: cert.id,
      notice: "cancelled",
    });
  });

  it("PIN bloqueado es terminal", () => {
    const awaiting = run(validating, { type: "awaiting_pin", challenges: [challenge] });
    expect(run(awaiting, { type: "pin_locked" }).name).toBe("pin_locked");
  });

  it("tiempo agotado: volver a empezar valida el mismo certificado", () => {
    const completing = run(validating, { type: "awaiting_pin", challenges: [challenge] }, { type: "completing" });
    const expired = run(completing, { type: "time_expired" });
    expect(expired.name).toBe("time_expired");
    expect(run(expired, { type: "revalidate" })).toMatchObject({ name: "validating", certificate: { id: cert.id } });
  });

  it("eventos fuera de lugar no cambian el estado", () => {
    expect(run(initialState, { type: "rejected", code: "x" })).toEqual(initialState);
    expect(run(choosing, { type: "completing" })).toEqual(choosing);
    expect(run(choosing, { type: "pin_error", kind: "busy" })).toEqual(choosing);
  });
});

describe("local y cancelación", () => {
  it("firma local", () => {
    const confirm = run(initialState, { type: "context_loaded", context: makeContext({ provider: "local" }) });
    expect(run(confirm, { type: "local_working" }).name).toBe("working_local");
  });

  it("cancelar conserva el contexto", () => {
    expect(run(choosing, { type: "cancelled" })).toMatchObject({ name: "cancelled", context: ctx });
  });

  it("solo se puede cancelar antes de que la firma esté hecha", () => {
    expect(isCancellable(choosing)).toBe(true);
    expect(isCancellable(run(choosing, { type: "validating" }))).toBe(false);
    expect(isCancellable({ name: "success", context: signedContext() })).toBe(false);
  });

  it("failed conserva el contexto cuando existe", () => {
    expect(run(choosing, { type: "failed", code: "x" })).toMatchObject({ name: "failed", context: ctx });
    expect(run(initialState, { type: "failed", code: "x" })).toEqual({ name: "failed", code: "x" });
  });
});
