import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "./styles/tokens.css";
import "./styles/app.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { createAgentClient } from "./api/agentClient";
import { createBatchServerClient, createServerClient } from "./api/serverClient";
import { linkFromPath, newSessionRef, takeToken } from "./bootstrap/token";
import { Notice } from "./components/Notice";
import { saveFile } from "./download";
import { createHostNotifier } from "./embed/hostMessages";
import { INVALID_LINK } from "./messages/es";

// El token se toma ANTES de renderizar: queda solo en memoria y se borra de la URL y del historial.
const token = takeToken(window.location, window.history);
const link = linkFromPath(window.location.pathname);

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("falta el elemento #root");
const root = createRoot(rootElement);

if (!token || !link) {
  root.render(
    <StrictMode>
      <main className="shell">
        <Notice message={INVALID_LINK} />
      </main>
    </StrictMode>,
  );
} else {
  const services = {
    server: (link.kind === "batch" ? createBatchServerClient : createServerClient)({
      requestId: link.id,
      token,
      sessionRef: newSessionRef(),
    }),
    createAgent: (agentUrl: string) => createAgentClient({ baseUrl: agentUrl }),
    createHost: (origins: string[], id: string) => createHostNotifier(origins, id),
    saveFile,
  };
  root.render(
    <StrictMode>
      <App services={services} />
    </StrictMode>,
  );
}
