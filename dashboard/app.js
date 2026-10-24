const $ = id => document.getElementById(id);
const state = { status: null, usage: null };

const baseUrl = () => $("#base").value.trim().replace(/\/+$/, "");

async function request(path, options = {}) {
  const response = await fetch(baseUrl() + path, {
    ...options,
    headers: {
      Authorization: "Bearer " + $("#admin").value.trim(),
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  let data;
  try { data = await response.json(); }
  catch { data = { detail: response.statusText || "Unexpected response" }; }
  if (!response.ok) {
    const error = new Error(data.detail || "Request failed (" + response.status + ")");
    error.status = response.status;
    throw error;
  }
  return data;
}

function notice(message, type = "") {
  const element = $("#notice");
  element.textContent = message;
  element.className = "notice " + type;
}

function escapeHtml(value) {
  const element = document.createElement("span");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

function formatTime(timestamp) {
  const date = new Date(Number(timestamp) * 1000);
  return Number.isNaN(date.valueOf()) ? "—" : date.toLocaleString();
}

async function connect(event) {
  event?.preventDefault();
  if (!$("#base").value.trim() || !$("#admin").value.trim()) {
    notice("Enter the API base URL and admin bearer password.", "error");
    return;
  }
  notice("Connecting securely to your engine…");
  $("#engine").textContent = "…";
  try {
    const [status, usage] = await Promise.all([
      request("/admin/status"),
      request("/admin/usage"),
    ]);
    state.status = status;
    state.usage = usage;
    render();
    notice("Connected. Live engine details are up to date.", "ok");
  } catch (error) {
    $("#engine").textContent = "Offline";
    notice(error.message, "error");
  }
}

function render() {
  const status = state.status || {};
  const usage = state.usage || {};
  $("#engine").textContent = "Online";
  $("#backend").textContent = "Inference backend · " + (status.backend || "unknown");
  $("#model").textContent = status.model || "Not selected";
  $("#requests").textContent = Number(usage.total_requests || 0).toLocaleString();

  const models = Array.isArray(status.models) ? status.models : [];
  $("#model-count").textContent = models.length + " model" + (models.length === 1 ? "" : "s") + " available";
  $("#models-list").innerHTML = models.length
    ? models.map(model => {
        const name = typeof model === "string" ? model : model.name || model.model || "Model";
        return '<span class="model-chip"><i></i>' + escapeHtml(name) + "</span>";
      }).join("")
    : '<div class="empty">No models are currently advertised by your provider.</div>';

  const recent = Array.isArray(usage.recent) ? usage.recent : [];
  $("#activity-list").innerHTML = recent.length
    ? recent.slice(0, 6).map(item =>
        '<div class="activity-row"><span>' + escapeHtml(item.endpoint || "API request") +
        "</span><time>" + escapeHtml(formatTime(item.created)) + "</time></div>"
      ).join("")
    : '<div class="empty">No requests recorded yet. Make an API call to see activity.</div>';

  const keys = Array.isArray(usage.keys) ? usage.keys : [];
  $("#key-list").innerHTML = keys.length
    ? keys.map(key => {
        const action = key.revoked
          ? '<small class="revoked">Revoked</small>'
          : '<button class="revoke-key" type="button" data-key-id="' + escapeHtml(key.id) + '">Revoke</button>';
        return '<div class="key-row"><strong>' + escapeHtml(key.label || "API key") +
          ' <small>···' + escapeHtml(key.id || "") + "</small></strong><span>" +
          action + ' <small>' + escapeHtml(formatTime(key.created)) + "</small></span></div>";
      }).join("")
    : '<div class="empty">No generated keys yet.</div>';
}

async function makeKey(event) {
  event.preventDefault();
  $("#key-result").textContent = "Creating key…";
  try {
    const key = await request(
      "/admin/keys?label=" + encodeURIComponent($("#label").value.trim() || "API key"),
      { method: "POST" },
    );
    $("#key-result").innerHTML =
      "New key: <code>" + escapeHtml(key.key) + '</code> <button type="button" id="copy-key">Copy</button>' +
      " <span>Copy it now; it will not be shown again.</span>";
    $("#copy-key").addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(key.key);
        $("#copy-key").textContent = "Copied";
      } catch {
        $("#key-result").insertAdjacentText("beforeend", " Clipboard unavailable; select and copy the key manually.");
      }
    });
    await connect();
  } catch (error) {
    $("#key-result").textContent = error.message;
  }
}

async function revokeKey(id) {
  if (!window.confirm("Revoke this API key? Applications using it will lose access.")) return;
  try {
    await request("/admin/keys/" + encodeURIComponent(id), { method: "DELETE" });
    await connect();
    notice("API key revoked.", "ok");
  } catch (error) {
    notice(error.message, "error");
  }
}

$("#connect-form").addEventListener("submit", connect);
$("#key-form").addEventListener("submit", makeKey);
$("#refresh").addEventListener("click", connect);
$("#key-list").addEventListener("click", event => {
  const button = event.target.closest(".revoke-key");
  if (button) revokeKey(button.dataset.keyId);
});
