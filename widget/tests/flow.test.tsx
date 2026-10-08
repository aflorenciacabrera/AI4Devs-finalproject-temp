import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";

import { App } from "../src/App";
import { AgentError, AgentUnreachableError, ServerError } from "../src/api/errors";
import {
  challenge,
  makeCert,
  makeContext,
  makeFakes,
  signedContext,
  type Fakes,
} from "./fixtures";

const NOW = new Date("2026-10-08T12:00:00Z");

function mount(fakes: Fakes) {
  return render(<App services={fakes.services} now={() => NOW} />);
}

const heading = (name: string | RegExp) => screen.findByRole("heading", { name, level: 1 });
const click = (name: string | RegExp) => userEvent.click(screen.getByRole("button", { name }));

async function untilChoosing(fakes: Fakes) {
  mount(fakes);
  await heading("Elegí el certificado");
}

describe("firma con el proveedor local", () => {
  it("confirma, firma en un solo paso y muestra el resultado del servidor", async () => {
    const fakes = makeFakes(makeContext({ provider: "local" }));
    mount(fakes);
    await heading("Firmar el documento");
    expect(screen.getAllByText(/firma electrónica de demostración/i).length).toBeGreaterThan(0);

    await click("Firmar");
    await heading("Documento firmado correctamente");

    expect(fakes.server.prepare).toHaveBeenCalledWith(); // sin certificado
    expect(fakes.server.complete).toHaveBeenCalledWith([]); // sin firmas: firma el servidor
    expect(fakes.agent.certificates).not.toHaveBeenCalled(); // nunca toca al agente
    expect(fakes.host.signed).toHaveBeenCalledOnce();

    // datos tal como los informa el servidor, sin inventar valores
    expect(screen.getByText("PAdES B-B")).toBeInTheDocument();
    expect(screen.getByText(/v2 · vigente/)).toBeInTheDocument();
    expect(screen.getByText(/Las versiones anteriores se conservan/)).toBeInTheDocument();
    expect(screen.queryByText(/B-LT/)).not.toBeInTheDocument();
  });

  it("un error del servidor se muestra y se avisa al anfitrión sin detalles internos", async () => {
    const fakes = makeFakes(makeContext({ provider: "local" }));
    fakes.server.complete.mockRejectedValue(new ServerError("http_500", 500, "Traceback secreto"));
    mount(fakes);
    await heading("Firmar el documento");
    await click("Firmar");
    await heading("No se pudo completar la firma");
    expect(screen.queryByText(/Traceback/)).not.toBeInTheDocument();
    expect(fakes.host.failed).toHaveBeenCalledWith("http_500");
  });
});

describe("firma con token", () => {
  it("lista los certificados, valida, firma con el agente y completa", async () => {
    const fakes = makeFakes();
    await untilChoosing(fakes);
    expect(fakes.host.ready).toHaveBeenCalledOnce();
    expect(screen.getByText(/Firmadoc Agent conectado/)).toBeInTheDocument();
    expect(screen.getByText("María Fernanda Ríos")).toBeInTheDocument();
    expect(screen.getByText("CUIL 27-12345678-4")).toBeInTheDocument();
    expect(screen.getByText("Emisor: AC Demo")).toBeInTheDocument();

    await click("Validar y continuar");
    await heading("Documento firmado correctamente");

    expect(fakes.server.prepare).toHaveBeenCalledWith(makeCert().certificate_pem);
    expect(fakes.agent.sign).toHaveBeenCalledWith("SERIE1:01", [challenge]);
    expect(fakes.server.complete).toHaveBeenCalledWith([
      { challenge_id: challenge.challenge_id, signature_base64: "U0lHTkFUVVJB" },
    ]);
    expect(fakes.host.signed).toHaveBeenCalledOnce();
  });

  it("deshabilita y explica los certificados vencidos", async () => {
    const fakes = makeFakes();
    fakes.agent.certificates.mockResolvedValue([
      makeCert({ id: "A", subject: "CN=Vencida,C=AR", not_after: "2025-05-05T12:00:00+00:00" }),
      makeCert({ id: "B", subject: "CN=Vigente,C=AR" }),
    ]);
    await untilChoosing(fakes);
    const expired = screen.getByRole("radio", { name: /Vencida/ });
    expect(expired).toBeDisabled();
    expect(screen.getByText(/Venció el 05\/05\/2025/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Vigente/ })).toBeChecked(); // preselecciona el vigente
  });

  it("si todos están vencidos no se puede continuar", async () => {
    const fakes = makeFakes();
    fakes.agent.certificates.mockResolvedValue([makeCert({ not_after: "2025-05-05T12:00:00+00:00" })]);
    await untilChoosing(fakes);
    expect(screen.getByRole("button", { name: "Validar y continuar" })).toBeDisabled();
  });

  it("cambiar de certificado envía el elegido", async () => {
    const fakes = makeFakes();
    fakes.agent.certificates.mockResolvedValue([
      makeCert({ id: "A", subject: "CN=Primera,C=AR", certificate_pem: "PEM-A" }),
      makeCert({ id: "B", subject: "CN=Segunda,C=AR", certificate_pem: "PEM-B" }),
    ]);
    await untilChoosing(fakes);
    await userEvent.click(screen.getByRole("radio", { name: /Segunda/ }));
    await click("Validar y continuar");
    await heading("Documento firmado correctamente");
    expect(fakes.server.prepare).toHaveBeenCalledWith("PEM-B");
    expect(fakes.agent.sign).toHaveBeenCalledWith("B", expect.anything());
  });
});

describe("agente", () => {
  it("no detectado: muestra las comprobaciones y permite reintentar", async () => {
    const fakes = makeFakes();
    fakes.agent.certificates.mockRejectedValueOnce(new AgentUnreachableError());
    mount(fakes);
    await heading("No detectamos Firmadoc Agent");
    expect(screen.getByText("Firmadoc Agent instalado y en ejecución")).toBeInTheDocument();
    expect(screen.getByText(/Token conectado/)).toBeInTheDocument();
    expect(screen.getByText(/Permiso de acceso a la red local/)).toBeInTheDocument();

    await click("Reintentar detección");
    await heading("Elegí el certificado");
    expect(fakes.agent.certificates).toHaveBeenCalledTimes(2);
  });

  it.each([
    [[], "No encontramos el token", null],
    [null, "Este sitio no está autorizado en tu agente", "origin_not_allowed"],
    [null, "No se puede usar el software del token", "pkcs11_unavailable"],
    [null, "No encontramos el token", "token_not_found"],
  ])("problemas del agente (%j / %s)", async (list, title, code) => {
    const fakes = makeFakes();
    if (list) fakes.agent.certificates.mockResolvedValue(list);
    else fakes.agent.certificates.mockRejectedValue(new AgentError(code!, 403, "x"));
    mount(fakes);
    await heading(title);
    expect(screen.getByRole("button", { name: "Reintentar detección" })).toBeInTheDocument();
    expect(fakes.agent.sign).not.toHaveBeenCalled();
  });
});

describe("certificado rechazado antes del PIN", () => {
  it.each([
    ["certificate_revoked", "Certificado revocado"],
    ["certificate_expired", "Certificado vencido"],
    ["certificate_untrusted", "Autoridad certificante no confiable"],
    ["cuil_mismatch", "CUIL distinto al del firmante"],
  ])("%s", async (code, reason) => {
    const fakes = makeFakes();
    fakes.server.prepare.mockRejectedValue(new ServerError(code, code === "cuil_mismatch" ? 403 : 422, "x"));
    await untilChoosing(fakes);
    await click("Validar y continuar");

    await heading("El certificado no pudo validarse");
    expect(screen.getByText(reason)).toBeInTheDocument();
    expect(within(screen.getByRole("main")).getByText(/No se te pidió el PIN/)).toBeInTheDocument();
    expect(fakes.agent.sign).not.toHaveBeenCalled(); // nunca se llegó a pedir el PIN
  });

  it("elegir otro certificado vuelve a la lista sin recargar", async () => {
    const fakes = makeFakes();
    fakes.server.prepare.mockRejectedValueOnce(new ServerError("certificate_revoked", 422, "x"));
    fakes.agent.certificates.mockResolvedValue([
      makeCert({ id: "A", subject: "CN=Revocada,C=AR" }),
      makeCert({ id: "B", subject: "CN=Buena,C=AR" }),
    ]);
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("El certificado no pudo validarse");
    await click("Elegir otro certificado");
    await heading("Elegí el certificado");
    expect(screen.getByRole("radio", { name: /Buena/ })).toBeChecked();
    expect(fakes.server.getContext).toHaveBeenCalledOnce(); // no se perdió la sesión
  });
});

describe("firma en el agente", () => {
  it("cancelar en el agente vuelve a la lista con un aviso, no es un error", async () => {
    const fakes = makeFakes();
    fakes.agent.sign.mockRejectedValue(new AgentError("user_cancelled", 409, "x"));
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("Elegí el certificado");
    expect(screen.getByText(/Cancelaste la firma en el agente/)).toBeInTheDocument();
    expect(fakes.host.failed).not.toHaveBeenCalled();
  });

  it("PIN incorrecto: un solo intento, reintento solo con el botón y sin volver a preparar", async () => {
    const fakes = makeFakes();
    fakes.agent.sign
      .mockRejectedValueOnce(new AgentError("pin_incorrect", 401, "x"))
      .mockResolvedValue([{ challenge_id: challenge.challenge_id, signature_base64: "U0lH" }]);
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("PIN incorrecto");

    await new Promise((r) => setTimeout(r, 150)); // si hubiera un reintento automático, ocurriría acá
    expect(fakes.agent.sign).toHaveBeenCalledTimes(1);

    await click("Reintentar");
    await heading("Documento firmado correctamente");
    expect(fakes.agent.sign).toHaveBeenCalledTimes(2);
    expect(fakes.server.prepare).toHaveBeenCalledTimes(1); // mismos desafíos
  });

  it("PIN bloqueado es terminal y no ofrece reintentar", async () => {
    const fakes = makeFakes();
    fakes.agent.sign.mockRejectedValue(new AgentError("pin_locked", 423, "x"));
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("El token está bloqueado");
    expect(screen.queryByRole("button", { name: /reintentar/i })).not.toBeInTheDocument();
    expect(screen.getByText(/administrador del token/)).toBeInTheDocument();
  });

  it("agente ocupado", async () => {
    const fakes = makeFakes();
    fakes.agent.sign.mockRejectedValue(new AgentError("busy", 429, "x"));
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("Ya hay una firma esperando confirmación");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("el agente desaparece durante la firma", async () => {
    const fakes = makeFakes();
    fakes.agent.sign.mockRejectedValue(new AgentUnreachableError());
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("No detectamos Firmadoc Agent");
  });

  it("desafío vencido: ofrece volver a empezar con el mismo certificado", async () => {
    const fakes = makeFakes();
    fakes.server.complete
      .mockRejectedValueOnce(new ServerError("http_409", 409, "venció"))
      .mockResolvedValue(signedContext());
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("Se agotó el tiempo para firmar");

    await click("Volver a empezar");
    await heading("Documento firmado correctamente");
    expect(fakes.server.prepare).toHaveBeenCalledTimes(2);
    expect(fakes.server.prepare).toHaveBeenLastCalledWith(makeCert().certificate_pem);
  });

  it("firma rechazada por el servidor", async () => {
    const fakes = makeFakes();
    fakes.server.complete.mockRejectedValue(new ServerError("http_422", 422, "no verifica"));
    await untilChoosing(fakes);
    await click("Validar y continuar");
    await heading("No se pudo completar la firma");
    expect(fakes.host.failed).toHaveBeenCalled();
  });
});

describe("otros estados", () => {
  it("método no soportado: no se intenta nada", async () => {
    const fakes = makeFakes(makeContext({ provider: "firmar" }));
    const createAgent = vi.fn(fakes.services.createAgent);
    fakes.services.createAgent = createAgent;
    mount(fakes);
    await heading("Este método de firma no está disponible");
    expect(createAgent).not.toHaveBeenCalled();
    expect(fakes.server.prepare).not.toHaveBeenCalled();
  });

  it.each([401, 403])("enlace inválido o vencido (HTTP %s)", async (status) => {
    const fakes = makeFakes();
    fakes.server.getContext.mockRejectedValue(new ServerError("invalid_token", status, "x"));
    mount(fakes);
    await heading("El enlace de firma no es válido o venció");
    expect(screen.queryByRole("button", { name: /reintentar/i })).not.toBeInTheDocument();
    expect(fakes.host.ready).not.toHaveBeenCalled();
  });

  it("solicitud ya firmada muestra el resultado", async () => {
    const fakes = makeFakes(signedContext());
    mount(fakes);
    await heading("Documento firmado correctamente");
    expect(fakes.agent.certificates).not.toHaveBeenCalled();
  });

  it("cancelar antes de firmar avisa al anfitrión y no firma", async () => {
    const fakes = makeFakes();
    await untilChoosing(fakes);
    await click("Cancelar");
    await heading("Firma cancelada");
    expect(fakes.host.cancelled).toHaveBeenCalledOnce();
    expect(fakes.agent.sign).not.toHaveBeenCalled();
    expect(fakes.server.prepare).not.toHaveBeenCalled();
  });

  it("descargar usa el servidor y entrega el archivo; cerrar avisa al anfitrión", async () => {
    const fakes = makeFakes(makeContext({ provider: "local" }));
    mount(fakes);
    await heading("Firmar el documento");
    await click("Firmar");
    await heading("Documento firmado correctamente");

    await click("Descargar PDF firmado");
    await waitFor(() => expect(fakes.saveFile).toHaveBeenCalledOnce());
    expect(fakes.saveFile.mock.calls[0]![1]).toBe("firmado.pdf");

    await click("Cerrar");
    expect(fakes.host.closed).toHaveBeenCalledOnce();
  });

  it("si la descarga falla lo informa y permite reintentar", async () => {
    const fakes = makeFakes(makeContext({ provider: "local" }));
    fakes.server.downloadPdf.mockRejectedValueOnce(new ServerError("network_error", 0, "x"));
    mount(fakes);
    await heading("Firmar el documento");
    await click("Firmar");
    await heading("Documento firmado correctamente");
    await click("Descargar PDF firmado");
    expect(await screen.findByRole("alert")).toHaveTextContent(/No se pudo descargar/);
    await click("Descargar PDF firmado");
    await waitFor(() => expect(fakes.saveFile).toHaveBeenCalledOnce());
  });
});

describe("accesibilidad", () => {
  const scenarios: [string, () => Fakes, string | RegExp, (() => Promise<void>)?][] = [
    ["lista de certificados", () => makeFakes(), "Elegí el certificado"],
    [
      "agente no detectado",
      () => {
        const f = makeFakes();
        f.agent.certificates.mockRejectedValue(new AgentUnreachableError());
        return f;
      },
      "No detectamos Firmadoc Agent",
    ],
    [
      "certificado rechazado",
      () => {
        const f = makeFakes();
        f.server.prepare.mockRejectedValue(new ServerError("certificate_revoked", 422, "x"));
        return f;
      },
      "El certificado no pudo validarse",
      async () => click("Validar y continuar"),
    ],
    [
      "PIN incorrecto",
      () => {
        const f = makeFakes();
        f.agent.sign.mockRejectedValue(new AgentError("pin_incorrect", 401, "x"));
        return f;
      },
      "PIN incorrecto",
      async () => click("Validar y continuar"),
    ],
    ["firma local", () => makeFakes(makeContext({ provider: "local" })), "Firmar el documento"],
    [
      "firma completada",
      () => makeFakes(signedContext()),
      "Documento firmado correctamente",
    ],
    [
      "enlace inválido",
      () => {
        const f = makeFakes();
        f.server.getContext.mockRejectedValue(new ServerError("invalid_token", 401, "x"));
        return f;
      },
      "El enlace de firma no es válido o venció",
    ],
    ["método no soportado", () => makeFakes(makeContext({ provider: "firmar" })), "Este método de firma no está disponible"],
  ];

  it.each(scenarios)("sin violaciones automáticas: %s", async (_name, make, title, act) => {
    const fakes = make();
    const { container } = mount(fakes);
    await heading(title === "El certificado no pudo validarse" || title === "PIN incorrecto" ? "Elegí el certificado" : title);
    if (act) {
      await act();
      await heading(title);
    }
    expect((await axe(container)).violations).toEqual([]); // sin violaciones de accesibilidad
  });

  it("el foco queda en el título de cada pantalla y el cambio se anuncia", async () => {
    const fakes = makeFakes();
    await untilChoosing(fakes);
    const title = screen.getByRole("heading", { level: 1 });
    expect(title).toHaveFocus();
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Elegí el certificado"));

    fakes.server.prepare.mockRejectedValue(new ServerError("certificate_revoked", 422, "x"));
    await click("Validar y continuar");
    const next = await heading("El certificado no pudo validarse");
    await waitFor(() => expect(next).toHaveFocus());
    expect(within(screen.getByRole("status")).getByText(/Motivo: Certificado revocado/)).toBeInTheDocument();
  });

  it("se puede completar el flujo solo con el teclado", async () => {
    const fakes = makeFakes();
    await untilChoosing(fakes);
    await userEvent.tab(); // radio
    await userEvent.tab(); // Cancelar
    await userEvent.tab(); // Validar y continuar
    expect(screen.getByRole("button", { name: "Validar y continuar" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    await heading("Documento firmado correctamente");
  });
});
