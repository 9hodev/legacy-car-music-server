/**
 * Network Dashboard & Device Monitoring Client JavaScript
 * Real-time polling, device heartbeat, activity logs pagination, and admin authentication
 */

var currentPage = 1;
var totalPages = 1;
var statsTimer = null;
var heartbeatTimer = null;
var currentSessionToken = localStorage.getItem("admin_session_token") || "";

// DOM Elements
var statStatus = document.getElementById("stat-status");
var statHostPort = document.getElementById("stat-host-port");
var statUptime = document.getElementById("stat-uptime");
var statOnlineDevices = document.getElementById("stat-online-devices");
var statRegisteredDevices = document.getElementById("stat-registered-devices");
var statConnections = document.getElementById("stat-connections");
var statActiveTransfers = document.getElementById("stat-active-transfers");
var statUpSpeed = document.getElementById("stat-up-speed");
var statDownSpeed = document.getElementById("stat-down-speed");
var statTotalUploaded = document.getElementById("stat-total-uploaded");
var statTotalDownloaded = document.getElementById("stat-total-downloaded");

var transfersContainer = document.getElementById("transfers-container");
var transfersBadge = document.getElementById("transfers-badge");
var devicesTbody = document.getElementById("devices-tbody");
var devicesBadge = document.getElementById("devices-badge");

var logsTbody = document.getElementById("logs-tbody");
var logsCountBadge = document.getElementById("logs-count-badge");
var logSearch = document.getElementById("log-search");
var logEventFilter = document.getElementById("log-event-filter");
var btnPrevPage = document.getElementById("btn-prev-page");
var btnNextPage = document.getElementById("btn-next-page");
var paginationText = document.getElementById("pagination-text");

var authModal = document.getElementById("auth-modal");
var authSecretInput = document.getElementById("auth-secret-input");
var authErrorMsg = document.getElementById("auth-error-msg");
var btnAuthToggle = document.getElementById("btn-auth-toggle");
var authStatusDesc = document.getElementById("auth-status-desc");
var btnLoginOpen = document.getElementById("btn-login-open");
var btnLogout = document.getElementById("btn-logout");
var serverUrlDisplay = document.getElementById("server-url-display");
var toast = document.getElementById("toast");

// Lock View Elements
var lockView = document.getElementById("dashboard-lock-view");
var contentView = document.getElementById("dashboard-content-view");
var lockSecretInput = document.getElementById("lock-secret-input");
var lockErrorMsg = document.getElementById("lock-error-msg");

document.addEventListener("DOMContentLoaded", function () {
  initDeviceRegistration();
  checkAuthStatus();
});

// ----------------------------------------------------------------------
// Device Discovery & Heartbeat
// ----------------------------------------------------------------------
function getPersistentDeviceId() {
  var id = localStorage.getItem("local_music_device_id");
  if (!id) {
    id = "dev_" + Math.random().toString(36).substring(2, 10);
    localStorage.setItem("local_music_device_id", id);
  }
  return id;
}

function detectDeviceType() {
  var ua = navigator.userAgent.toLowerCase();
  if (ua.indexOf("android") !== -1) {
    return ua.indexOf("mobile") === -1 ? "car" : "mobile";
  }
  if (ua.indexOf("iphone") !== -1 || ua.indexOf("ipad") !== -1) return "mobile";
  return "desktop";
}

function initDeviceRegistration() {
  var deviceId = getPersistentDeviceId();
  var devType = detectDeviceType();
  var name = "Dashboard Client (" + (navigator.platform || "Desktop") + ")";

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/devices/register", true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.send(JSON.stringify({
    device_id: deviceId,
    name: name,
    device_type: devType
  }));
}

function sendHeartbeat() {
  var deviceId = getPersistentDeviceId();
  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/devices/heartbeat", true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.send(JSON.stringify({
    device_id: deviceId,
    current_activity: "Viewing Dashboard"
  }));
}

// ----------------------------------------------------------------------
// Stats Loader
// ----------------------------------------------------------------------
function loadStats() {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/dashboard/stats", true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    if (xhr.status === 401) {
      showLockScreen();
      return;
    }
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success && resp.stats) {
          updateStatsUI(resp.stats);
        }
      } catch (e) {}
    }
  };
  xhr.send();
}

function updateStatsUI(s) {
  if (statStatus) statStatus.textContent = s.server_status || "Running";
  if (statHostPort) statHostPort.textContent = s.server_ip + ":" + s.server_port;
  if (statUptime) statUptime.textContent = s.uptime_formatted || "00h 00m 00s";
  if (statOnlineDevices) statOnlineDevices.textContent = s.online_device_count;
  if (statRegisteredDevices) statRegisteredDevices.textContent = s.total_registered_devices + " registered total";
  if (statConnections) statConnections.textContent = s.active_connections;
  if (statActiveTransfers) statActiveTransfers.textContent = s.active_transfers_count + " live file transfers";

  if (statUpSpeed) statUpSpeed.textContent = formatBytes(s.upload_throughput_bps) + "/s";
  if (statDownSpeed) statDownSpeed.textContent = formatBytes(s.download_throughput_bps) + "/s";
  if (statTotalUploaded) statTotalUploaded.textContent = "Total: " + formatBytes(s.total_uploaded_bytes);
  if (statTotalDownloaded) statTotalDownloaded.textContent = "Total: " + formatBytes(s.total_downloaded_bytes);

  if (serverUrlDisplay && s.server_ip) {
    serverUrlDisplay.value = "http://" + s.server_ip + ":" + s.server_port;
  }

  renderLiveTransfers(s.active_transfers || []);
}

function renderLiveTransfers(transfers) {
  if (!transfersContainer) return;

  if (transfersBadge) {
    transfersBadge.textContent = transfers.length + " active";
  }

  if (transfers.length === 0) {
    transfersContainer.innerHTML = '<div class="table-empty">No active uploads or downloads right now.</div>';
    return;
  }

  var html = "";
  for (var i = 0; i < transfers.length; i++) {
    var t = transfers[i];
    var safeName = escapeHtml(t.filename);
    var isUp = (t.type === "upload");
    var badgeClass = isUp ? "badge-primary" : "badge-secondary";
    var icon = isUp ? "&#11014; Upload" : "&#11015; Download";
    var pct = Math.round(t.progress || 0);
    var speedStr = formatBytes(t.speed || 0) + "/s";
    var etaStr = t.eta > 0 ? " • ETA: " + Math.round(t.eta) + "s" : "";

    html += '<div class="transfer-row">' +
      '<div class="transfer-header">' +
        '<div class="transfer-title">' +
          '<span class="badge ' + badgeClass + '">' + icon + '</span>' +
          '<strong>' + safeName + '</strong>' +
          '<span class="text-muted">(' + t.client_ip + ')</span>' +
        '</div>' +
        '<div class="transfer-meta">' + pct + '% • ' + speedStr + etaStr + '</div>' +
      '</div>' +
      '<div class="progress-bar-track">' +
        '<div class="progress-bar-fill" style="width: ' + pct + '%;"></div>' +
      '</div>' +
    '</div>';
  }

  transfersContainer.innerHTML = html;
}

// ----------------------------------------------------------------------
// Devices Loader
// ----------------------------------------------------------------------
function loadDevices() {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/devices", true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    if (xhr.status === 401) {
      showLockScreen();
      return;
    }
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        renderDevicesTable(resp.devices || []);
      } catch (e) {}
    }
  };
  xhr.send();
}

function renderDevicesTable(devices) {
  if (!devicesTbody) return;

  if (devicesBadge) {
    devicesBadge.textContent = devices.length + " devices";
  }

  if (devices.length === 0) {
    devicesTbody.innerHTML = '<tr><td colspan="6" class="table-empty">No devices registered yet. Devices appear as soon as they connect to the server.</td></tr>';
    return;
  }

  var html = "";
  for (var i = 0; i < devices.length; i++) {
    var d = devices[i];
    var isOnline = d.online_status;
    var statusBadge = isOnline
      ? '<span class="status-dot status-online"></span> Online'
      : '<span class="status-dot status-offline"></span> Offline';

    var isRevoked = d.revoked;
    var actionBtn = isRevoked
      ? '<span class="badge badge-warning">Revoked</span>'
      : '<button class="btn btn-danger btn-small" onclick="revokeDevice(\'' + escapeJsString(d.device_id) + '\')">Revoke</button>';

    var typeIcon = "&#128187; Desktop";
    if (d.device_type === "mobile") typeIcon = "&#128241; Mobile";
    if (d.device_type === "car") typeIcon = "&#128663; Car Unit";

    html += '<tr>' +
      '<td><strong>' + escapeHtml(d.name) + '</strong></td>' +
      '<td><code>' + escapeHtml(d.ip_address) + '</code></td>' +
      '<td>' + typeIcon + '</td>' +
      '<td>' + statusBadge + '</td>' +
      '<td>' + escapeHtml(d.last_seen_formatted) + '<br><small class="text-muted">' + escapeHtml(d.current_activity) + '</small></td>' +
      '<td style="text-align: right;">' + actionBtn + '</td>' +
    '</tr>';
  }

  devicesTbody.innerHTML = html;
}

function revokeDevice(deviceId) {
  if (!confirm("Are you sure you want to revoke this device? It will be blocked from accessing the server.")) {
    return;
  }

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/devices/revoke", true);
  xhr.setRequestHeader("Content-Type", "application/json");
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }

  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      showToast("Device revoked successfully");
      loadDevices();
    } else {
      var err = "Revoke failed (Status " + xhr.status + ")";
      try { err = JSON.parse(xhr.responseText).error || err; } catch (e) {}
      alert(err);
    }
  };
  xhr.send(JSON.stringify({ device_id: deviceId }));
}

// ----------------------------------------------------------------------
// Activity Logs Loader
// ----------------------------------------------------------------------
function onFilterChange() {
  currentPage = 1;
  loadLogs(1);
}

function prevPage() {
  if (currentPage > 1) {
    loadLogs(currentPage - 1);
  }
}

function nextPage() {
  if (currentPage < totalPages) {
    loadLogs(currentPage + 1);
  }
}

function loadLogs(page) {
  currentPage = page || 1;
  var search = logSearch ? logSearch.value.trim() : "";
  var eventType = logEventFilter ? logEventFilter.value : "";

  var url = "/api/logs?page=" + currentPage + "&limit=15";
  if (search) url += "&search=" + encodeURIComponent(search);
  if (eventType) url += "&event_type=" + encodeURIComponent(eventType);

  var xhr = new XMLHttpRequest();
  xhr.open("GET", url, true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    if (xhr.status === 401) {
      showLockScreen();
      return;
    }
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        totalPages = resp.total_pages || 1;
        renderLogsTable(resp.logs || [], resp.total || 0);
        updatePagination(resp.page, totalPages);
      } catch (e) {}
    }
  };
  xhr.send();
}

function renderLogsTable(logs, totalCount) {
  if (!logsTbody) return;

  if (logsCountBadge) {
    logsCountBadge.textContent = totalCount + " records";
  }

  if (logs.length === 0) {
    logsTbody.innerHTML = '<tr><td colspan="5" class="table-empty">No activity records match the current filter.</td></tr>';
    return;
  }

  var html = "";
  for (var i = 0; i < logs.length; i++) {
    var l = logs[i];
    var statusClass = "badge-secondary";
    if (l.status === "success") statusClass = "badge-primary";
    if (l.status === "failed") statusClass = "badge-warning";
    if (l.status === "warning") statusClass = "badge-warning";

    var detailStr = l.filename ? '<strong>' + escapeHtml(l.filename) + '</strong>' : '';
    if (l.file_size) detailStr += ' (' + formatBytes(l.file_size) + ')';
    if (l.error_details) detailStr += '<br><small style="color:#ff7b72;">' + escapeHtml(l.error_details) + '</small>';
    if (!detailStr) detailStr = '<span class="text-muted">-</span>';

    html += '<tr>' +
      '<td>' + escapeHtml(l.timestamp_formatted) + '</td>' +
      '<td><code>' + escapeHtml(l.event_type) + '</code></td>' +
      '<td><code>' + escapeHtml(l.client_ip) + '</code></td>' +
      '<td>' + detailStr + '</td>' +
      '<td><span class="badge ' + statusClass + '">' + escapeHtml(l.status) + '</span></td>' +
    '</tr>';
  }

  logsTbody.innerHTML = html;
}

function updatePagination(page, total) {
  if (paginationText) {
    paginationText.textContent = "Page " + page + " of " + total;
  }
  if (btnPrevPage) btnPrevPage.disabled = (page <= 1);
  if (btnNextPage) btnNextPage.disabled = (page >= total);
}

function exportLogsCsv() {
  window.location.href = "/api/logs/export";
}

function confirmClearLogs() {
  if (!confirm("Are you sure you want to permanently clear all activity logs? This action cannot be undone.")) {
    return;
  }

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/logs/clear", true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      showToast("Activity logs cleared.");
      loadLogs(1);
    } else {
      var err = "Clear logs failed (Status " + xhr.status + ")";
      try { err = JSON.parse(xhr.responseText).error || err; } catch (e) {}
      alert(err);
    }
  };
  xhr.send();
}

// ----------------------------------------------------------------------
// Authentication Handling & Dashboard Gate
// ----------------------------------------------------------------------
function checkAuthStatus() {
  var xhr = new XMLHttpRequest();
  xhr.open("GET", "/api/auth/status", true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.authenticated) {
          showDashboardContent();
        } else {
          showLockScreen();
        }
      } catch (e) {
        showLockScreen();
      }
    } else {
      showLockScreen();
    }
  };
  xhr.onerror = function () {
    showLockScreen();
  };
  xhr.send();
}

function showDashboardContent() {
  if (lockView) lockView.style.display = "none";
  if (contentView) contentView.style.display = "block";
  updateAuthUI(true);

  loadStats();
  loadDevices();
  loadLogs(1);

  if (!statsTimer) {
    statsTimer = setInterval(loadStats, 2500);
  }
  if (!heartbeatTimer) {
    heartbeatTimer = setInterval(sendHeartbeat, 12000);
  }
}

function showLockScreen() {
  if (statsTimer) {
    clearInterval(statsTimer);
    statsTimer = null;
  }
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
  if (contentView) contentView.style.display = "none";
  if (lockView) lockView.style.display = "flex";
  if (lockSecretInput) {
    lockSecretInput.value = "";
    lockSecretInput.focus();
  }
  if (lockErrorMsg) lockErrorMsg.style.display = "none";
  updateAuthUI(false);
}

function submitLockAuth() {
  var secret = lockSecretInput ? lockSecretInput.value.trim() : "";
  if (!secret) return;

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/auth/login", true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success && resp.token) {
          currentSessionToken = resp.token;
          localStorage.setItem("admin_session_token", resp.token);
          showToast("Dashboard unlocked successfully!");
          showDashboardContent();
        } else {
          showLockError(resp.error || "Authentication failed.");
        }
      } catch (e) {
        showLockError("Error parsing server response.");
      }
    } else {
      var err = "Authentication failed (Status " + xhr.status + ")";
      try { err = JSON.parse(xhr.responseText).error || err; } catch (e) {}
      showLockError(err);
    }
  };
  xhr.onerror = function () {
    showLockError("Network connection error.");
  };
  xhr.send(JSON.stringify({ secret: secret }));
}

function showLockError(msg) {
  if (!lockErrorMsg) return;
  lockErrorMsg.textContent = msg;
  lockErrorMsg.style.display = "block";
}

function updateAuthUI(isAuth) {
  if (isAuth) {
    if (btnAuthToggle) btnAuthToggle.textContent = "Logout Admin";
    if (btnAuthToggle) btnAuthToggle.onclick = logoutAdmin;
    if (authStatusDesc) authStatusDesc.innerHTML = "<strong style='color:#00e676;'>Authenticated Admin Session</strong>";
    if (btnLoginOpen) btnLoginOpen.style.display = "none";
    if (btnLogout) btnLogout.style.display = "inline-flex";
  } else {
    if (btnAuthToggle) btnAuthToggle.textContent = "Admin Login";
    if (btnAuthToggle) btnAuthToggle.onclick = openAuthModal;
    if (authStatusDesc) authStatusDesc.innerHTML = "<span class='text-muted'>Locked (Authentication required)</span>";
    if (btnLoginOpen) btnLoginOpen.style.display = "inline-flex";
    if (btnLogout) btnLogout.style.display = "none";
  }
}

function openAuthModal() {
  authErrorMsg.style.display = "none";
  authSecretInput.value = "";
  authModal.style.display = "flex";
  authSecretInput.focus();
}

function closeAuthModal() {
  authModal.style.display = "none";
}

function submitAuth() {
  var secret = authSecretInput.value.trim();
  if (!secret) return;

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/auth/login", true);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      try {
        var resp = JSON.parse(xhr.responseText);
        if (resp.success && resp.token) {
          currentSessionToken = resp.token;
          localStorage.setItem("admin_session_token", resp.token);
          closeAuthModal();
          showToast("Admin authenticated successfully!");
          showDashboardContent();
        } else {
          showAuthError(resp.error || "Authentication failed.");
        }
      } catch (e) {
        showAuthError("Error parsing server response.");
      }
    } else {
      var err = "Authentication failed (Status " + xhr.status + ")";
      try { err = JSON.parse(xhr.responseText).error || err; } catch (e) {}
      showAuthError(err);
    }
  };
  xhr.onerror = function () {
    showAuthError("Network connection error.");
  };
  xhr.send(JSON.stringify({ secret: secret }));
}

function showAuthError(msg) {
  authErrorMsg.textContent = msg;
  authErrorMsg.style.display = "block";
}

function logoutAdmin() {
  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/auth/logout", true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    currentSessionToken = "";
    localStorage.removeItem("admin_session_token");
    showToast("Logged out from Admin session.");
    showLockScreen();
  };
  xhr.send();
}

function confirmStopServer() {
  if (!confirm("Are you sure you want to shut down the server process? You will need to start it again from Terminal.")) {
    return;
  }

  var xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/server/stop", true);
  if (currentSessionToken) {
    xhr.setRequestHeader("X-Admin-Token", currentSessionToken);
  }
  xhr.onload = function () {
    if (xhr.status >= 200 && xhr.status < 300) {
      alert("Server is shutting down cleanly.");
    } else {
      var err = "Shutdown request failed";
      try { err = JSON.parse(xhr.responseText).error || err; } catch (e) {}
      alert(err);
    }
  };
  xhr.send();
}

function copyServerUrl() {
  var el = serverUrlDisplay;
  if (!el) return;
  el.select();
  document.execCommand("copy");
  showToast("Server URL copied to clipboard!");
}

// ----------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------
function showToast(message) {
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  setTimeout(function () {
    toast.classList.remove("show");
  }, 2800);
}

function formatBytes(bytes) {
  if (bytes === 0 || !bytes) return "0 B";
  var k = 1024;
  var sizes = ["B", "KB", "MB", "GB", "TB"];
  var i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function escapeHtml(text) {
  if (!text) return "";
  var div = document.createElement("div");
  div.appendChild(document.createTextNode(text));
  return div.innerHTML;
}

function escapeJsString(str) {
  if (!str) return "";
  return str.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
}

