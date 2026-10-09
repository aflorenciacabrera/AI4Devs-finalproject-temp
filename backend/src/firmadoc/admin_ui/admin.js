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
      const td = el("td", c.node ? null : c.get ? c.get(row) : fmt(row[c.key]));
      if (c.node) td.appendChild(c.node(row));
      if (c.mono) td.className = "mono";
      tr.appendChild(td);
    }
    if (rowActions) {
      const actionCell = el("td");
      for (const node of rowActions(row)) actionCell.appendChild(node);
      tr.appendChild(actionCell);
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

const STATUS_LABELS = { signed: "Firmado", pending: "Pendiente", signing: "Firmando", failed: "Fallido" };
const PROVIDER_LABELS = { token: "Token", local: "Propio", firmar: "FirmAR" };

function chip(text, kind) {
  return el("span", text, { class: "chip " + kind });
}

function dateOnly(value) {
  return value ? new Date(value).toLocaleDateString("es-AR") : "";
}

function timeOnly(value) {
  return value ? new Date(value).toLocaleTimeString("es-AR") : "";
}

function cell(...nodes) {
  const wrap = el("span");
  for (const n of nodes) wrap.appendChild(n);
  return wrap;
}

async function loadRequests() {
  $("documents-list").hidden = false;
  $("document-detail").hidden = true;
  const q = params($("requests-filters"));
  q.set("limit", PAGE);
  q.set("offset", requestsOffset);
  const data = await api("GET", "/signature-requests?" + q);
  requestsTotal = data.total;
  replace($("requests-table"), table([
    { label: "Documento", node: (r) => cell(el("span", r.document.external_document_id || r.document.id), el("small", "v" + fmt(r.document.current_version_number), { class: "cell-sub" })) },
    { label: "Firmante", node: (r) => cell(el("span", r.signer.name), el("small", r.signer.identifier, { class: "cell-sub" })) },
    { label: "Fecha", node: (r) => cell(el("span", dateOnly(r.created_at)), el("small", timeOnly(r.created_at), { class: "cell-sub" })) },
    { label: "Proveedor", get: (r) => PROVIDER_LABELS[r.provider] || r.provider },
    { label: "Origen", get: (r) => (r.origin.kind === "batch" ? "Lote " + r.origin.label : "Individual") },
    {
      label: "Estado",
      node: (r) => {
        const nodes = [chip(STATUS_LABELS[r.status] || r.status, r.status)];
        if (r.status === "pending" && r.document.signature_deadline) nodes.push(el("small", "Vence " + dateOnly(r.document.signature_deadline), { class: "cell-sub" }));
        return cell(...nodes);
      },
    },
  ], data.items, (r) => {
    const open = el("button", "Ver detalle", { type: "button" });
    open.addEventListener("click", () => loadCustody(r.document.id).catch((e) => { if (e.message !== "unauthorized") show(e.message, "bad"); }));
    return [open];
  }));
  const from = data.total ? requestsOffset + 1 : 0;
  $("requests-page").textContent = from + "-" + Math.min(requestsOffset + PAGE, data.total) + " de " + data.total;
  $("requests-prev").disabled = requestsOffset === 0;
  $("requests-next").disabled = requestsOffset + PAGE >= data.total;
}

async function downloadVersion(documentId, number) {
  const response = await fetch(API + "/documents/" + encodeURIComponent(documentId) + "/versions/" + number + "/download", {
    headers: { Authorization: "Bearer " + token },
    cache: "no-store",
    credentials: "omit",
  });
  if (response.status === 401) { logout("Acceso denegado: el token de administración no es válido."); return; }
  if (!response.ok) throw new Error("No se pudo descargar la versión (" + response.status + ").");
  const match = /filename="?([^";]+)"?/i.exec(response.headers.get("content-disposition") || "");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = match ? match[1] : "documento-v" + number + ".pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadButton(documentId, number, label) {
  const button = el("button", label, { type: "button" });
  button.addEventListener("click", () => downloadVersion(documentId, number).catch((e) => show(e.message, "bad")));
  return button;
}

async function loadCustody(documentId) {
  const data = await api("GET", "/documents/" + encodeURIComponent(documentId) + "/custody");
  const doc = data.document;
  const box = el("div");

  const back = el("button", "← Volver a Documentos", { type: "button" });
  back.addEventListener("click", () => { loadRequests().catch((e) => { if (e.message !== "unauthorized") show(e.message, "bad"); }); });
  box.appendChild(back);

  const head = el("div", null, { class: "detail-head" });
  const title = el("div");
  title.appendChild(el("h2", doc.external_document_id || doc.id));
  title.appendChild(el("div", "ID " + doc.id + (doc.integrating_system_name ? " · " + doc.integrating_system_name : ""), { class: "muted" }));
  head.appendChild(title);
  const actions = el("div", null, { class: "row-actions" });
  actions.appendChild(chip(STATUS_LABELS[doc.signing_status] || ({ draft: "Borrador", pending_signature: "Pendiente de firma", signed: "Firmado" })[doc.signing_status] || doc.signing_status, doc.signing_status === "signed" ? "signed" : "pending"));
  const current = data.versions.find((v) => v.is_current);
  if (current && current.signature_level) actions.appendChild(downloadButton(doc.id, current.version_number, "Descargar PDF firmado"));
  head.appendChild(actions);
  box.appendChild(head);
  if (doc.signature_deadline) box.appendChild(el("p", "Vence " + dateOnly(doc.signature_deadline), { class: "muted" }));

  const grid = el("div", null, { class: "detail-grid" });

  const custody = el("div", null, { class: "card" });
  custody.appendChild(el("h3", "Cadena de custodia"));
  const timeline = el("ol", null, { class: "timeline" });
  for (const t of data.timeline) {
    const item = el("li", null, { class: t.kind });
    item.appendChild(el("span", dateOnly(t.at) + " " + timeOnly(t.at) + " · " + t.actor, { class: "when" }));
    item.appendChild(el("span", t.title, { class: "title" }));
    if (t.detail) item.appendChild(el("span", t.detail, { class: "detail" }));
    timeline.appendChild(item);
  }
  if (!data.timeline.length) timeline.appendChild(el("li", "Sin eventos registrados."));
  custody.appendChild(timeline);
  grid.appendChild(custody);

  const side = el("div");
  const versions = el("div", null, { class: "card" });
  versions.appendChild(el("h3", "Versiones"));
  for (const v of [...data.versions].reverse()) {
    const row = el("div", null, { class: "version-row" });
    const label = el("span", "v" + v.version_number + " · " + (v.signature_level ? "firmada (PAdES " + v.signature_level + ")" : "original subida") + " · " + dateOnly(v.created_at) + " " + timeOnly(v.created_at));
    row.appendChild(label);
    const right = el("span", null, { class: "row-actions" });
    if (v.is_current) right.appendChild(chip("Vigente", "active"));
    right.appendChild(downloadButton(doc.id, v.version_number, "Descargar"));
    row.appendChild(right);
    versions.appendChild(row);
  }
  side.appendChild(versions);

  const tech = el("div", null, { class: "card" });
  tech.appendChild(el("h3", "Detalle técnico"));
  const kv = el("dl", null, { class: "kv" });
  const t = data.technical;
  const rows = t
    ? [
        ["ID de transacción", t.transaction_id],
        ["Proveedor", PROVIDER_LABELS[t.provider] || t.provider],
        ["Nivel de firma", t.signature_level ? "PAdES " + t.signature_level : "-"],
        ["Certificado", t.certificate ? t.certificate.subject : "-"],
        ["Emisor", t.certificate ? t.certificate.issuer_subject + " · serie " + t.certificate.serial_number : "-"],
        ["Hash original (SHA-256)", t.original_hash],
        ["Hash documento firmado", t.signed_hash],
        ["Firmante", t.signer ? t.signer.name + " (" + t.signer.identifier + ")" : "-"],
      ]
    : [["Estado", "Todavía no hay una firma completada."]];
  for (const [k, v] of rows) { kv.appendChild(el("dt", k)); kv.appendChild(el("dd", fmt(v))); }
  tech.appendChild(kv);
  side.appendChild(tech);
  grid.appendChild(side);
  box.appendChild(grid);

  $("documents-list").hidden = true;
  $("document-detail").hidden = false;
  replace($("document-detail"), box);
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

// --- Integradores -----------------------------------------------------------------------------

function originsList(text) {
  return text.split(/[\n,]/).map((o) => o.trim()).filter(Boolean);
}

function hideCredentials() {
  const box = $("credentials");
  box.textContent = "";  // las credenciales no se guardan en ningún lado: solo viven en esta pantalla
  box.hidden = true;
}

function showCredentials(title, entries) {
  const box = $("credentials");
  box.textContent = "";
  box.appendChild(el("strong", title));
  box.appendChild(el("p", "Guardalas ahora: no se vuelven a mostrar.", { class: "muted" }));
  for (const [label, value] of entries) {
    box.appendChild(el("div", label));
    box.appendChild(el("code", value));
    const copy = el("button", "Copiar " + label, { type: "button" });
    copy.addEventListener("click", () => {
      if (navigator.clipboard) navigator.clipboard.writeText(value).then(() => show("Copiado.", "ok"), () => show("No se pudo copiar: seleccionalo a mano.", "bad"));
    });
    box.appendChild(copy);
  }
  const close = el("button", "Ya las guardé", { type: "button", class: "primary" });
  close.addEventListener("click", hideCredentials);
  box.appendChild(close);
  box.hidden = false;
}

async function loadIntegrators() {
  const data = await api("GET", "/integrators");
  replace($("integrators-table"), table([
    { label: "Nombre", get: (i) => i.name + (i.internal ? " (interno)" : "") },
    { label: "Orígenes permitidos", get: (i) => (i.allowed_origins.length ? i.allowed_origins.join(", ") : "-") },
    { label: "Estado", node: (i) => chip(i.status === "active" ? "Activo" : "Deshabilitado", i.status) },
  ], data, (i) => {
    if (i.internal) return [];
    const wrap = el("span", null, { class: "row-actions" });
    const edit = el("button", "Editar orígenes", { type: "button" });
    edit.addEventListener("click", () => {
      const form = $("origins-form");
      form.dataset.id = i.id;
      $("origins-name").textContent = i.name;
      form.elements.origins.value = i.allowed_origins.join("\n");
      form.hidden = false;
      form.elements.origins.focus();
    });
    const secret = el("button", "Rotar secreto de webhook", { type: "button" });
    secret.addEventListener("click", async () => {
      if (!confirm("¿Rotar el secreto de webhook de " + i.name + "? El sistema deberá usar el nuevo para validar las notificaciones.")) return;
      try {
        const r = await api("POST", "/integrators/" + i.id + "/rotate-webhook-secret");
        showCredentials("Nuevo secreto de webhook de " + i.name, [["Secreto de webhook", r.webhook_secret]]);
        await loadIntegrators();
      } catch (e) { if (e.message !== "unauthorized") show(e.message, "bad"); }
    });
    const key = el("button", "Rotar API key", { type: "button", class: "danger" });
    key.addEventListener("click", async () => {
      if (!confirm("¿Rotar la API key de " + i.name + "? La anterior deja de funcionar de inmediato.")) return;
      try {
        const r = await api("POST", "/integrators/" + i.id + "/rotate-api-key");
        showCredentials("Nueva API key de " + i.name, [["API key", r.api_key]]);
        await loadIntegrators();
      } catch (e) { if (e.message !== "unauthorized") show(e.message, "bad"); }
    });
    const toggle = el("button", i.status === "active" ? "Deshabilitar" : "Habilitar", { type: "button", class: i.status === "active" ? "danger" : "" });
    toggle.addEventListener("click", async () => {
      const disabling = i.status === "active";
      if (disabling && !confirm("¿Deshabilitar a " + i.name + "? No podrá usar la API hasta que lo habilites de nuevo.")) return;
      await act(() => api("POST", "/integrators/" + i.id + (disabling ? "/disable" : "/enable")), disabling ? "Integrador deshabilitado." : "Integrador habilitado.", loadIntegrators);
    });
    for (const b of [edit, secret, key, toggle]) wrap.appendChild(b);
    return [wrap];
  }));
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

const LOADERS = {
  sign: async () => {},
  documents: loadRequests,
  audit: () => Promise.all([loadWebhooks(), loadEvents()]),
  integrators: async () => { hideCredentials(); $("origins-form").hidden = true; await loadIntegrators(); },
  trust: () => Promise.all([loadAnchors(), loadCertificate()]),
};

function switchTab(name) {
  for (const section of document.querySelectorAll("[id^='tab-']")) section.hidden = section.id !== "tab-" + name;
  for (const b of document.querySelectorAll(".sidebar button")) b.setAttribute("aria-current", String(b.dataset.tab === name));
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
  $("sign-docs").hidden = true;
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

let staged = [];

function isPdf(file) {
  return file.type === "application/pdf" || /\.pdf$/i.test(file.name);
}

function renderStaged() {
  const list = $("sign-staged-list");
  list.textContent = "";
  staged.forEach((file, index) => {
    const item = el("li");
    item.appendChild(el("span", file.name, { class: "file-name" }));
    item.appendChild(el("span", formatSize(file.size), { class: "muted" }));
    const remove = el("button", "Quitar", { type: "button" });
    remove.addEventListener("click", () => { staged.splice(index, 1); renderStaged(); });
    item.appendChild(remove);
    list.appendChild(item);
  });
  $("sign-staged-count").textContent = String(staged.length);
  $("sign-staged-go").textContent = staged.length > 1 ? "Cargar y firmar " + staged.length + " documentos" : "Cargar y firmar documento";
  $("sign-staged").hidden = staged.length === 0;
}

function clearStaged() {
  staged = [];
  renderStaged();
}

function showReady(name, meta, signingUrl, documents) {
  resetSign();
  $("sign-name").textContent = name;
  $("sign-meta").textContent = meta;
  const docs = $("sign-docs");
  docs.textContent = "";
  docs.hidden = !documents;
  for (const d of documents || []) {
    const item = el("li");
    item.appendChild(el("span", d.filename, { class: "file-name" }));
    item.appendChild(el("span", d.page_count + (d.page_count === 1 ? " página" : " páginas") + " · " + formatSize(d.size_bytes), { class: "muted" }));
    docs.appendChild(item);
  }
  $("sign-upload").hidden = true;
  $("sign-ready").hidden = false;
  mountWidget(signingUrl);
}

async function uploadFiles(files) {
  try {
    const documents = [];
    for (const file of files) documents.push({ filename: file.name, document_base64: await readBase64(file) });
    if (documents.length === 1) {
      const data = await api("POST", "/signing-uploads", documents[0]);
      showReady(data.filename, data.page_count + (data.page_count === 1 ? " página" : " páginas") + " · " + formatSize(data.size_bytes), data.signing_url, null);
    } else {
      const data = await api("POST", "/signing-batch-uploads", { documents });
      showReady(data.documents.length + " documentos", "Firma en lote: un solo PIN para todos", data.signing_url, data.documents);
    }
    clearStaged();
  } catch (e) {
    if (e.message !== "unauthorized") show(e.message, "bad");
  }
}

// Un solo PDF se carga enseguida; con varios se arma la lista (se puede quitar alguno) antes de cargar.
function chooseFiles(fileList) {
  show("");
  const files = Array.from(fileList || []);
  if (files.length === 0) return;
  const bad = files.find((f) => !isPdf(f));
  if (bad) { show("«" + bad.name + "» no es un PDF: solo se pueden cargar archivos PDF.", "bad"); return; }
  const big = files.find((f) => f.size > MAX_PDF_BYTES);
  if (big) { show("«" + big.name + "» supera el tamaño máximo de " + formatSize(MAX_PDF_BYTES) + ".", "bad"); return; }
  if (files.length === 1 && staged.length === 0) { uploadFiles(files); return; }
  staged.push(...files);
  renderStaged();
}

// Solo se atienden mensajes de la ventana del iframe y del propio origen.
window.addEventListener("message", (event) => {
  if (!signFrame || event.source !== signFrame.contentWindow || event.origin !== location.origin) return;
  const data = event.data;
  if (!data || data.source !== "firmadoc") return;
  if (data.type === "firmadoc:signed") signResult("Documento firmado: quedó como nueva versión vigente. Descargalo desde el módulo de firma.", "ok");
  else if (data.type === "firmadoc:batch-completed") {
    const signed = Number(data.signed) || 0;
    const total = Number(data.total) || 0;
    signResult(signed + " de " + total + " documentos firmados." + (signed < total ? " Podés reintentar los fallidos desde el módulo de firma." : ""), signed === total ? "ok" : "bad");
  }
  else if (data.type === "firmadoc:failed") signResult("La firma falló" + (data.code ? " (" + String(data.code) + ")" : "") + ".", "bad");
  else if (data.type === "firmadoc:cancelled") signResult("Firma cancelada. El documento quedó guardado sin firmar.", "bad");
});

$("sign-file").addEventListener("change", (event) => { chooseFiles(event.target.files); event.target.value = ""; });
$("sign-drop").addEventListener("dragover", (event) => { event.preventDefault(); $("sign-drop").classList.add("over"); });
$("sign-drop").addEventListener("dragleave", () => $("sign-drop").classList.remove("over"));
$("sign-drop").addEventListener("drop", (event) => {
  event.preventDefault();
  $("sign-drop").classList.remove("over");
  chooseFiles(event.dataTransfer.files);
});
$("sign-staged-clear").addEventListener("click", clearStaged);
$("sign-staged-go").addEventListener("click", () => { if (staged.length > 0) uploadFiles([...staged]); });
$("sign-remove").addEventListener("click", () => { resetSign(); clearStaged(); });
$("sign-replace").addEventListener("click", () => { resetSign(); clearStaged(); $("sign-file").click(); });

$("login-form").addEventListener("submit", (event) => { event.preventDefault(); login($("token").value.trim()); });
$("logout").addEventListener("click", () => logout(""));
$("theme").addEventListener("click", toggleTheme);
applyTheme(readTheme() || systemTheme());
for (const b of document.querySelectorAll(".sidebar button")) b.addEventListener("click", () => switchTab(b.dataset.tab));
$("requests-filters").addEventListener("submit", (event) => { event.preventDefault(); requestsOffset = 0; loadRequests().catch((e) => show(e.message, "bad")); });
$("requests-prev").addEventListener("click", () => { requestsOffset = Math.max(0, requestsOffset - PAGE); loadRequests(); });
$("requests-next").addEventListener("click", () => { if (requestsOffset + PAGE < requestsTotal) { requestsOffset += PAGE; loadRequests(); } });
$("webhooks-filters").addEventListener("submit", (event) => { event.preventDefault(); loadWebhooks(); });
$("integrator-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = $("integrator-form");
  try {
    const r = await api("POST", "/integrators", { name: form.elements.name.value.trim(), allowed_origins: originsList(form.elements.origins.value) });
    form.reset();
    showCredentials("Integrador «" + r.name + "» creado", [["API key", r.api_key], ["Secreto de webhook", r.webhook_secret]]);
    show("Integrador creado.", "ok");
    await loadIntegrators();
  } catch (e) { if (e.message !== "unauthorized") show(e.message, "bad"); }
});
$("origins-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = $("origins-form");
  await act(() => api("PATCH", "/integrators/" + form.dataset.id, { allowed_origins: originsList(form.elements.origins.value) }), "Orígenes actualizados.", async () => { form.hidden = true; await loadIntegrators(); });
});
$("origins-cancel").addEventListener("click", () => { $("origins-form").hidden = true; });
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
