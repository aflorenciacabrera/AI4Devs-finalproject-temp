"use strict";
// Panel de administración. Todo el contenido dinámico se construye con textContent (nunca como HTML).

const API = "/api/v1/admin";
const PAGE = 50;
const KEY = "firmadoc-admin-token";
const $ = (id) => document.getElementById(id);

let token = null;
let requestsOffset = 0;
let requestsTotal = 0;

function readToken() {
  try { return sessionStorage.getItem(KEY); } catch { return null; }
}
function saveToken(value) {
  try {
    if (value) sessionStorage.setItem(KEY, value); else sessionStorage.removeItem(KEY);
  } catch { /* sin almacenamiento: la sesión dura lo que dure la página */ }
}

// --- Tema claro / oscuro: sigue al sistema hasta que la persona elige; la elección queda en este navegador ---
const THEME_KEY = "firmadoc-admin-theme";

function systemTheme() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}
function readTheme() {
  try { const value = localStorage.getItem(THEME_KEY); return value === "dark" || value === "light" ? value : null; } catch { return null; }
}
function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const button = $("theme");
  const next = theme === "dark" ? "claro" : "oscuro";
  button.textContent = theme === "dark" ? "☀" : "☾";
  button.setAttribute("aria-label", "Cambiar a modo " + next);
  button.title = "Cambiar a modo " + next;
}
function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  applyTheme(next);
  try { localStorage.setItem(THEME_KEY, next); } catch { /* sin almacenamiento: vale para esta página */ }
}

function el(tag, text, attrs) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  return node;
}

function show(message, kind) {
  const box = $("message");
  box.textContent = message;
  box.className = kind || "";
  box.hidden = !message;
}

function fmt(value) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string" && /^\d{4}-\d\d-\d\dT/.test(value)) return new Date(value).toLocaleString("es-AR");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

async function api(method, path, body) {
  const options = { method, headers: { Authorization: "Bearer " + token } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(API + path, options);
  if (response.status === 401) {
    logout("Acceso denegado: el token de administración no es válido.");
    throw new Error("unauthorized");
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail ? String(data.detail) : "Error " + response.status);
  return data;
}

function table(columns, rows, rowActions) {
  const wrap = el("div", null, { class: "table-wrap" });
  const t = el("table");
  const head = el("tr");
  for (const c of columns) head.appendChild(el("th", c.label));
  if (rowActions) head.appendChild(el("th", "Acciones"));
  t.appendChild(head);
  if (!rows.length) {
    const tr = el("tr");
    tr.appendChild(el("td", "Sin resultados", { colspan: columns.length + (rowActions ? 1 : 0) }));
    t.appendChild(tr);
  }
  for (const row of rows) {
    const tr = el("tr");
    for (const c of columns) {
      const cell = el("td", c.get ? c.get(row) : fmt(row[c.key]));
      if (c.mono) cell.className = "mono";
      tr.appendChild(cell);
    }
    if (rowActions) {
      const cell = el("td");
      for (const node of rowActions(row)) cell.appendChild(node);
      tr.appendChild(cell);
    }
    t.appendChild(tr);
  }
  wrap.appendChild(t);
  return wrap;
}

function replace(container, node) {
  container.replaceChildren(node);
}

function params(form) {
  const q = new URLSearchParams();
  for (const [k, v] of new FormData(form)) {
    if (!v) continue;
    if (k === "created_to") q.set(k, v + "T23:59:59Z");
    else if (k === "created_from") q.set(k, v + "T00:00:00Z");
    else q.set(k, v);
  }
  return q;
}

// --- secciones --------------------------------------------------------------------------------

async function loadRequests() {
  const q = params($("requests-filters"));
  q.set("limit", PAGE);
  q.set("offset", requestsOffset);
  const data = await api("GET", "/signature-requests?" + q);
  requestsTotal = data.total;
  replace($("requests-table"), table([
    { label: "Fecha", get: (r) => fmt(r.created_at) },
    { label: "Integrador", get: (r) => r.integrating_system.name },
    { label: "Documento", get: (r) => r.document.external_document_id || r.document.id },
    { label: "Estado doc.", get: (r) => r.document.signing_status },
    { label: "Versión", get: (r) => fmt(r.document.current_version_number) },
    { label: "Firmante", get: (r) => r.signer.name + " (" + r.signer.identifier + ")" },
    { label: "Proveedor", key: "provider" },
    { label: "Estado", key: "status" },
    { label: "Certificado", get: (r) => (r.certificate ? r.certificate.subject : "-") },
  ], data.items, (r) => {
    const open = el("button", "Ver custodia", { type: "button" });
    open.addEventListener("click", () => { $("custody-form").elements.document_id.value = r.document.id; switchTab("custody"); $("custody-form").requestSubmit(); });
    return [open];
  }));
  const from = data.total ? requestsOffset + 1 : 0;
  $("requests-page").textContent = from + "-" + Math.min(requestsOffset + PAGE, data.total) + " de " + data.total;
  $("requests-prev").disabled = requestsOffset === 0;
  $("requests-next").disabled = requestsOffset + PAGE >= data.total;
}

async function loadCustody(documentId) {
  const data = await api("GET", "/documents/" + encodeURIComponent(documentId) + "/custody");
  const box = el("div");
  const doc = el("div", null, { class: "card" });
  doc.appendChild(el("h3", "Documento " + (data.document.external_document_id || data.document.id)));
  doc.appendChild(el("div", "Estado de firma: " + data.document.signing_status + " · Plazo: " + fmt(data.document.signature_deadline)));
  box.appendChild(doc);
  box.appendChild(el("h3", "Versiones"));
  box.appendChild(table([
    { label: "N°", key: "version_number" }, { label: "Origen", key: "origin" },
    { label: "Nivel", key: "signature_level" }, { label: "Vigente", get: (v) => (v.is_current ? "sí" : "no") },
    { label: "SHA-256", key: "document_hash", mono: true }, { label: "Fecha", get: (v) => fmt(v.created_at) },
  ], data.versions));
  for (const r of data.signature_requests) {
    const card = el("div", null, { class: "card" });
    card.appendChild(el("h3", "Solicitud " + r.id + " · " + r.provider + " · " + r.status));
    card.appendChild(el("div", "Creada: " + fmt(r.created_at) + " · Firmada: " + fmt(r.signed_at)));
    card.appendChild(table([{ label: "Evento", key: "event_type" }, { label: "Detalle", key: "payload" }, { label: "Fecha", get: (e) => fmt(e.created_at) }], r.events));
    card.appendChild(table([{ label: "Desafío", key: "id", mono: true }, { label: "Vence", get: (c) => fmt(c.expires_at) }, { label: "Usado", get: (c) => fmt(c.consumed_at) }], r.challenges));
    card.appendChild(table([{ label: "Webhook", key: "event_type" }, { label: "Estado", key: "status" }, { label: "Intentos", key: "attempts" }, { label: "Último error", key: "last_error" }], r.webhook_deliveries));
    box.appendChild(card);
  }
  replace($("custody-result"), box);
}

async function loadWebhooks() {
  const q = params($("webhooks-filters"));
  q.set("limit", 100);
  const data = await api("GET", "/webhook-deliveries?" + q);
  replace($("webhooks-table"), table([
    { label: "Creada", get: (d) => fmt(d.created_at) }, { label: "Evento", key: "event_type" },
    { label: "URL", key: "url", mono: true }, { label: "Estado", key: "status" }, { label: "Intentos", key: "attempts" },
    { label: "Próximo intento", get: (d) => fmt(d.next_attempt_at) }, { label: "Último error", key: "last_error" },
    { label: "HTTP", key: "response_status" },
  ], data.items, (d) => {
    if (d.status !== "failed") return [];
    const retry = el("button", "Reenviar", { type: "button" });
    retry.addEventListener("click", async () => {
      if (!confirm("¿Reenviar esta entrega de webhook?")) return;
      await act(() => api("POST", "/webhook-deliveries/" + d.id + "/retry"), "Entrega reencolada.", loadWebhooks);
    });
    return [retry];
  }));
}

async function loadAnchors() {
  const data = await api("GET", "/trust-anchors");
  replace($("anchors-table"), table([
    { label: "Tipo", get: (a) => (a.is_root ? "Raíz" : "Intermedia") }, { label: "Sujeto", key: "subject" },
    { label: "Vence", get: (a) => fmt(a.not_after) }, { label: "Huella SHA-256", key: "fingerprint", mono: true },
  ], data, (a) => {
    const remove = el("button", "Quitar", { type: "button", class: "danger" });
    remove.addEventListener("click", async () => {
      if (!confirm("¿Quitar esta ancla de confianza?\n" + a.subject)) return;
      await act(() => api("DELETE", "/trust-anchors/" + a.fingerprint), "Ancla quitada.", loadAnchors);
    });
    return [remove];
  }));
}

async function loadCertificate() {
  const data = await api("GET", "/local-certificate");
  const box = el("div");
  const current = el("div", null, { class: "card" });
  current.appendChild(el("h3", "Vigente"));
  current.appendChild(el("div", data.current ? data.current.subject + " · serie " + data.current.serial_number + " · vence " + fmt(data.current.not_after) : "Todavía no se generó (se crea con la primera firma)."));
  box.appendChild(current);
  box.appendChild(el("h3", "Archivados (siguen sirviendo para verificar firmas anteriores)"));
  box.appendChild(table([{ label: "Serie", key: "serial_number" }, { label: "Huella", key: "fingerprint", mono: true }, { label: "Vencía", get: (c) => fmt(c.not_after) }], data.archived));
  replace($("certificate-info"), box);
}

async function loadEvents() {
  const data = await api("GET", "/events?limit=100");
  replace($("events-table"), table([
    { label: "Fecha", get: (e) => fmt(e.created_at) }, { label: "Actor", key: "actor" },
    { label: "Acción", key: "action" }, { label: "Detalle", key: "detail" },
  ], data.items));
}

// --- flujo general ----------------------------------------------------------------------------

async function act(operation, okMessage, reload) {
  try {
    await operation();
    show(okMessage, "ok");
    await reload();
  } catch (e) {
    if (e.message !== "unauthorized") show(e.message, "bad");
  }
}

const LOADERS = { sign: async () => {}, requests: loadRequests, webhooks: loadWebhooks, anchors: loadAnchors, certificate: loadCertificate, events: loadEvents, custody: async () => {} };

function switchTab(name) {
  for (const section of document.querySelectorAll("[id^='tab-']")) section.hidden = section.id !== "tab-" + name;
  for (const b of document.querySelectorAll("nav button")) b.setAttribute("aria-current", String(b.dataset.tab === name));
  show("");
  LOADERS[name]().catch((e) => { if (e.message !== "unauthorized") show(e.message, "bad"); });
}

function logout(message) {
  token = null;
  saveToken(null);
  $("app").hidden = true;
  $("logout").hidden = true;
  $("login").hidden = false;
  $("token").value = "";
  const box = $("login-error");
  box.textContent = message || "";
  box.hidden = !message;
}

async function login(value) {
  token = value;
  try {
    await api("GET", "/events?limit=1");
  } catch (e) {
    if (e.message !== "unauthorized") logout("No se pudo ingresar: " + e.message);
    return;
  }
  saveToken(value);
  $("login").hidden = true;
  $("app").hidden = false;
  $("logout").hidden = false;
  $("login-error").hidden = true;
  switchTab("sign");
}

// --- Firmar documento: carga de un PDF y widget embebido -----------------------------------------------
const MAX_PDF_BYTES = 20 * 1024 * 1024;
let signFrame = null;

function formatSize(bytes) {
  return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
}

function resetSign() {
  if (signFrame) { signFrame.remove(); signFrame = null; }
  $("sign-widget").textContent = "";
  $("sign-file").value = "";
  $("sign-ready").hidden = true;
  $("sign-upload").hidden = false;
  const box = $("sign-result");
  box.hidden = true;
  box.textContent = "";
}

function signResult(message, kind) {
  const box = $("sign-result");
  box.textContent = message;
  box.className = kind;
  box.hidden = false;
}

function readBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(new Error("No se pudo leer el archivo."));
    reader.readAsDataURL(file);
  });
}

function mountWidget(signingUrl) {
  const frame = document.createElement("iframe");
  frame.title = "Firma de documento (Firmadoc)";
  frame.setAttribute("allow", "local-network-access; local-network; loopback-network");
  frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-downloads");
  frame.referrerPolicy = "no-referrer";
  frame.src = signingUrl;
  $("sign-widget").appendChild(frame);
  signFrame = frame;
}

async function chooseFile(file) {
  show("");
  if (!file) return;
  if (file.type !== "application/pdf" && !/\.pdf$/i.test(file.name)) { show("El archivo debe ser un PDF.", "bad"); return; }
  if (file.size > MAX_PDF_BYTES) { show("El PDF supera el tamaño máximo de " + formatSize(MAX_PDF_BYTES) + ".", "bad"); return; }
  try {
    const data = await api("POST", "/signing-uploads", { filename: file.name, document_base64: await readBase64(file) });
    resetSign();
    $("sign-name").textContent = data.filename;
    $("sign-meta").textContent = data.page_count + (data.page_count === 1 ? " página" : " páginas") + " · " + formatSize(data.size_bytes);
    $("sign-upload").hidden = true;
    $("sign-ready").hidden = false;
    mountWidget(data.signing_url);
  } catch (e) {
    if (e.message !== "unauthorized") show(e.message, "bad");
  }
}

// Solo se atienden mensajes de la ventana del iframe y del propio origen.
window.addEventListener("message", (event) => {
  if (!signFrame || event.source !== signFrame.contentWindow || event.origin !== location.origin) return;
  const data = event.data;
  if (!data || data.source !== "firmadoc") return;
  if (data.type === "firmadoc:signed") signResult("Documento firmado: quedó como nueva versión vigente. Descargalo desde el módulo de firma.", "ok");
  else if (data.type === "firmadoc:failed") signResult("La firma falló" + (data.code ? " (" + String(data.code) + ")" : "") + ".", "bad");
  else if (data.type === "firmadoc:cancelled") signResult("Firma cancelada. El documento quedó guardado sin firmar.", "bad");
});

$("sign-file").addEventListener("change", (event) => chooseFile(event.target.files[0]));
$("sign-drop").addEventListener("dragover", (event) => { event.preventDefault(); $("sign-drop").classList.add("over"); });
$("sign-drop").addEventListener("dragleave", () => $("sign-drop").classList.remove("over"));
$("sign-drop").addEventListener("drop", (event) => {
  event.preventDefault();
  $("sign-drop").classList.remove("over");
  const files = event.dataTransfer.files;
  if (files.length > 1) { show("Cargá un solo PDF por vez.", "bad"); return; }
  chooseFile(files[0]);
});
$("sign-remove").addEventListener("click", resetSign);
$("sign-replace").addEventListener("click", () => { resetSign(); $("sign-file").click(); });

$("login-form").addEventListener("submit", (event) => { event.preventDefault(); login($("token").value.trim()); });
$("logout").addEventListener("click", () => logout(""));
$("theme").addEventListener("click", toggleTheme);
applyTheme(readTheme() || systemTheme());
for (const b of document.querySelectorAll("nav button")) b.addEventListener("click", () => switchTab(b.dataset.tab));
$("requests-filters").addEventListener("submit", (event) => { event.preventDefault(); requestsOffset = 0; loadRequests().catch((e) => show(e.message, "bad")); });
$("requests-prev").addEventListener("click", () => { requestsOffset = Math.max(0, requestsOffset - PAGE); loadRequests(); });
$("requests-next").addEventListener("click", () => { if (requestsOffset + PAGE < requestsTotal) { requestsOffset += PAGE; loadRequests(); } });
$("custody-form").addEventListener("submit", (event) => { event.preventDefault(); loadCustody($("custody-form").elements.document_id.value.trim()).catch((e) => { if (e.message !== "unauthorized") show(e.message, "bad"); }); });
$("webhooks-filters").addEventListener("submit", (event) => { event.preventDefault(); loadWebhooks(); });
$("anchor-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const pem = $("anchor-pem").value;
  act(() => api("POST", "/trust-anchors", { certificate_pem: pem }), "Ancla agregada.", async () => { $("anchor-pem").value = ""; await loadAnchors(); });
});
$("rotate").addEventListener("click", () => {
  if (!confirm("¿Rotar el certificado propio? La clave vigente se destruye; las firmas anteriores siguen verificándose.")) return;
  act(() => api("POST", "/local-certificate/rotate"), "Certificado rotado.", loadCertificate);
});

const saved = readToken();
if (saved) login(saved);
