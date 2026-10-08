// Página anfitriona de ejemplo: embebe el widget por iframe o por Web Component y registra los mensajes.
// Este es el patrón recomendado para un sistema integrador: validar SIEMPRE el origen y la ventana.
(function () {
  const params = new URLSearchParams(window.location.hash.slice(1));
  const signingUrl = params.get("signing_url");
  const mode = params.get("mode") || "iframe";
  const slot = document.getElementById("slot");
  const log = document.getElementById("log");
  const status = document.getElementById("status");

  window.__messages = []; // la prueba de punta a punta lee esto

  function record(kind, data) {
    window.__messages.push({ kind, data });
    const item = document.createElement("li");
    item.textContent = kind + " " + JSON.stringify(data);
    log.appendChild(item);
    if (data && data.type === "firmadoc:signed") status.textContent = "Documento firmado";
    if (data && data.type === "firmadoc:cancelled") status.textContent = "Firma cancelada";
    if (data && data.type === "firmadoc:failed") status.textContent = "La firma falló";
  }

  if (!signingUrl) {
    status.textContent = "Falta signing_url en el fragmento.";
    return;
  }
  const widgetOrigin = new URL(signingUrl).origin;

  if (mode === "component") {
    // Opción 2: Web Component. widget.js se sirve desde el propio servidor de Firmadoc.
    const script = document.createElement("script");
    script.src = widgetOrigin + "/widget.js";
    script.onload = function () {
      const el = document.createElement("firmadoc-widget");
      el.setAttribute("signing-url", signingUrl);
      ["ready", "signed", "failed", "cancelled", "closed"].forEach(function (name) {
        el.addEventListener("firmadoc-" + name, function (event) {
          record("evento DOM firmadoc-" + name, event.detail);
        });
      });
      slot.appendChild(el);
    };
    document.head.appendChild(script);
  } else {
    // Opción 1: iframe. `allow` delega el permiso de red local para hablar con el agente (Chrome 142+).
    const frame = document.createElement("iframe");
    frame.title = "Firma de documento (Firmadoc)";
    frame.setAttribute("allow", "local-network-access; local-network; loopback-network");
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-downloads");
    frame.referrerPolicy = "no-referrer";
    frame.src = signingUrl;
    slot.appendChild(frame);

    window.addEventListener("message", function (event) {
      // Validar el emisor: la ventana del iframe Y el origen de Firmadoc.
      if (event.source !== frame.contentWindow || event.origin !== widgetOrigin) return;
      if (!event.data || event.data.source !== "firmadoc") return;
      record("postMessage", event.data);
    });
  }
})();
