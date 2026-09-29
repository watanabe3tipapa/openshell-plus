"use strict";

const state = {
  token: sessionStorage.getItem("osui_token") || "",
  config: null,
  sandboxes: [],
  selected: null,
  socket: null,
  timer: null,
  running: false,
};

const el = {
  connDot: document.getElementById("conn-dot"),
  chipMode: document.getElementById("chip-mode"),
  chipBackend: document.getElementById("chip-backend"),
  rows: document.getElementById("rows"),
  empty: document.getElementById("empty"),
  chipTarget: document.getElementById("chip-target"),
  cmd: document.getElementById("cmd"),
  btnRun: document.getElementById("btn-run"),
  console: document.getElementById("console-body"),
  statusLine: document.getElementById("status-line"),
  authPanel: document.getElementById("auth-panel"),
  authError: document.getElementById("auth-error"),
  footWorkspace: document.getElementById("foot-workspace"),
  transportHint: document.getElementById("transport-hint"),
};

function authHeaders(extra) {
  const headers = Object.assign({}, extra || {});
  if (state.token) headers["Authorization"] = `Bearer ${state.token}`;
  return headers;
}

async function api(path, options) {
  const opts = options || {};
  const response = await fetch(path, {
    method: opts.method || "GET",
    headers: authHeaders(
      opts.body ? { "Content-Type": "application/json" } : undefined
    ),
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (response.status === 401) {
    showAuthPanel("トークンが無効、または未入力です。");
    throw new Error("unauthorized");
  }
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = (payload && payload.detail) || response.statusText;
    write(`[error] ${detail}`, "err");
    throw new Error(detail);
  }
  return payload;
}

function write(text, cls) {
  const span = document.createElement("span");
  if (cls) span.className = cls;
  span.textContent = text;
  el.console.appendChild(span);
  el.console.parentElement.scrollTop = el.console.parentElement.scrollHeight;
}

function setStatus(text) {
  el.statusLine.textContent = text;
}

function setConnected(ok) {
  el.connDot.className = `dot ${ok ? "ok" : "bad"}`;
}

function showAuthPanel(message) {
  el.authPanel.hidden = false;
  el.authError.textContent = message || "";
  setConnected(false);
  document.getElementById("token-input").focus();
}

function hideAuthPanel() {
  el.authPanel.hidden = true;
  el.authError.textContent = "";
}

async function loadConfig() {
  const config = await api("/api/config");
  state.config = config;
  hideAuthPanel();
  el.chipMode.textContent = config.run_mode;
  el.chipBackend.textContent =
    config.backend === "demo" ? "demo backend" : "openshell gateway";
  el.footWorkspace.textContent = `workspace: ${config.workspace}`;
  const wsPath = config.capabilities.websocket;
  el.transportHint.textContent = wsPath
    ? "WebSocket でストリーミング受信します。"
    : "WebSocket は無効です。REST にフォールバックします。";
  if (config.backend === "demo") {
    write(
      "[info] デモバックエンドで動作中です。OpenShell gateway に接続すると実データが反映されます。",
      "sys"
    );
  }
  return config;
}

async function loadSandboxes() {
  const items = await api("/api/sandboxes");
  state.sandboxes = Array.isArray(items) ? items : [];
  renderRows();
  if (state.selected && !state.sandboxes.some((s) => s.name === state.selected)) {
    select(null);
  }
}

function badgeClass(phase) {
  return `badge badge-${phase}`;
}

function renderRows() {
  el.rows.replaceChildren();
  el.empty.hidden = state.sandboxes.length > 0;
  for (const box of state.sandboxes) {
    const row = document.createElement("tr");
    if (box.name === state.selected) row.className = "is-selected";

    const nameCell = document.createElement("td");
    nameCell.className = "name";
    nameCell.textContent = box.name;
    row.appendChild(nameCell);

    const phaseCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = badgeClass(box.phase);
    badge.textContent = box.phase;
    phaseCell.appendChild(badge);
    row.appendChild(phaseCell);

    const urlCell = document.createElement("td");
    const urls = Object.values(box.service_urls || {});
    if (urls.length) {
      const link = document.createElement("a");
      link.href = urls[0];
      link.textContent = urls[0].replace(/^https?:\/\//, "");
      link.target = "_blank";
      link.rel = "noreferrer noopener";
      urlCell.appendChild(link);
    } else {
      urlCell.textContent = "—";
      urlCell.className = "url";
    }
    row.appendChild(urlCell);

    const actionCell = document.createElement("td");
    const open = document.createElement("button");
    open.type = "button";
    open.className = "btn btn-ghost btn-sm";
    open.textContent = "選択";
    open.addEventListener("click", () => select(box.name));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "btn btn-ghost btn-sm";
    remove.textContent = "削除";
    remove.addEventListener("click", () => removeSandbox(box.name));
    actionCell.append(open, remove);
    row.appendChild(actionCell);

    row.addEventListener("click", () => select(box.name));
    el.rows.appendChild(row);
  }
}

function select(name) {
  state.selected = name;
  el.chipTarget.textContent = name || "サンドボックス未選択";
  const enabled = Boolean(name);
  el.cmd.disabled = !enabled;
  el.btnRun.disabled = !enabled;
  if (!enabled && state.socket) {
    state.socket.close();
    state.socket = null;
  }
  renderRows();
  if (name) el.cmd.focus();
}

async function removeSandbox(name) {
  if (!window.confirm(`サンドボックス ${name} を削除しますか？`)) return;
  await api(`/api/sandboxes/${encodeURIComponent(name)}`, { method: "DELETE" });
  write(`[info] ${name} を削除しました`, "sys");
  await loadSandboxes();
}

function execEndpoint(name) {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const url = new URL(`${scheme}://${window.location.host}/api/sandboxes/${encodeURIComponent(name)}/exec`);
  if (state.token) url.searchParams.set("token", state.token);
  return url;
}

async function runCommand(event) {
  event.preventDefault();
  const command = el.cmd.value.trim();
  if (!command || !state.selected || state.running) return;
  state.running = true;
  el.btnRun.disabled = true;
  setStatus("実行中…");
  const parts = command.split(/\s+/).filter(Boolean);
  write(`$ ${command}\n`, "sys");
  try {
    if (!state.config.capabilities.websocket) {
      const result = await api(`/api/sandboxes/${encodeURIComponent(state.selected)}/exec`, {
        method: "POST",
        body: { command: parts },
      });
      if (result.stdout) write(result.stdout);
      if (result.stderr) write(result.stderr, "err");
      write(`exit ${result.exit_code}\n`, result.exit_code === 0 ? "exit-ok" : "exit-bad");
    } else {
      await runOverWebSocket(parts);
    }
  } catch (err) {
    if (err.message !== "unauthorized") setStatus(err.message);
  } finally {
    state.running = false;
    el.btnRun.disabled = !state.selected;
  }
}

function runOverWebSocket(parts) {
  return new Promise((resolve) => {
    const socket = new WebSocket(execEndpoint(state.selected));
    state.socket = socket;
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ command: parts, timeout_seconds: 60 }));
    });
    socket.addEventListener("message", (message) => {
      let payload;
      try {
        payload = JSON.parse(message.data);
      } catch {
        return;
      }
      if (payload.type === "stdout" && payload.data) write(payload.data);
      else if (payload.type === "stderr" && payload.data) write(payload.data, "err");
      else if (payload.type === "exit") {
        write(`exit ${payload.exit_code}\n`, payload.exit_code === 0 ? "exit-ok" : "exit-bad");
        setStatus("");
        socket.close();
        resolve();
      } else if (payload.type === "error") {
        write(`[error] ${payload.detail}\n`, "err");
        setStatus("コマンドが失敗しました");
        socket.close();
        resolve();
      }
    });
    socket.addEventListener("close", () => {
      if (state.socket === socket) state.socket = null;
      if (state.running) setStatus("接続が切断されました。再実行できます。");
      resolve();
    });
    socket.addEventListener("error", () => {
      write("[error] WebSocket 接続に失敗しました\n", "err");
      resolve();
    });
  });
}

async function createSandbox(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const payload = { name: String(data.get("name") || "").trim() };
  const port = String(data.get("service_port") || "").trim();
  const service = String(data.get("service_name") || "").trim();
  if (port) payload.service_port = Number(port);
  if (service) payload.service_name = service;
  try {
    const created = await api("/api/sandboxes", { method: "POST", body: payload });
    write(`[info] ${created.name} を作成しました（${created.phase}）`, "sys");
    form.reset();
    await loadSandboxes();
    select(created.name);
  } catch {
    return;
  }
}

function scheduleRefresh() {
  if (state.timer) clearInterval(state.timer);
  const box = document.getElementById("auto-refresh");
  if (!box.checked) return;
  state.timer = setInterval(() => {
    if (!state.running && !state.socket) loadSandboxes().catch(() => {});
  }, 8000);
}

async function boot() {
  document.getElementById("form-exec").addEventListener("submit", runCommand);
  document.getElementById("form-create").addEventListener("submit", createSandbox);
  document.getElementById("btn-refresh").addEventListener("click", () =>
    loadSandboxes().catch(() => {})
  );
  document.getElementById("btn-clear").addEventListener("click", () => {
    el.console.textContent = "";
  });
  document.getElementById("auto-refresh").addEventListener("change", scheduleRefresh);
  document.getElementById("form-auth").addEventListener("submit", async (event) => {
    event.preventDefault();
    const value = document.getElementById("token-input").value.trim();
    if (!value) return;
    state.token = value;
    sessionStorage.setItem("osui_token", value);
    try {
      await loadConfig();
      await loadSandboxes();
      setConnected(true);
      write("[info] 認証しました", "sys");
    } catch {
      state.token = "";
      sessionStorage.removeItem("osui_token");
    }
  });

  try {
    await loadConfig();
    await loadSandboxes();
    setConnected(true);
  } catch {
    return;
  }
  scheduleRefresh();
}

boot();
