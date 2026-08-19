const state = {
  view: "dashboard",
  authMode: "login",
  user: JSON.parse(localStorage.getItem("generic-ml-user") || "null"),
  token: localStorage.getItem("generic-ml-token") || null,
  apiOnline: false,
  users: [],
  dashboardStats: null,
  selectedImageFile: null,
  logsState: {
    page: 1,
    limit: 20,
    pages: 1,
    total: 0,
  },
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function showToast(message, kind = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${kind}`;
  toast.textContent = message;
  $("#toast-region").append(toast);
  window.setTimeout(() => toast.remove(), 4200);
}

function setApiStatus(online) {
  state.apiOnline = online;
  const labels = [$("#dashboard-api-status"), $("#sidebar-status")];
  if (labels[0]) labels[0].textContent = online ? "Online" : "Offline";
  if (labels[1]) labels[1].textContent = online ? "API online" : "API offline";
  if ($("#dashboard-status-note")) {
    $("#dashboard-status-note").textContent = online ? "Backend is responding" : "Backend unavailable";
  }
  [$("#dashboard-status-dot"), $("#sidebar-status-dot")].forEach((dot) => {
    if (dot) {
      dot.classList.toggle("status-dot-online", online);
      dot.classList.toggle("status-dot-offline", !online);
    }
  });
}

async function apiRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  const response = await fetch(path, { headers, ...options });
  let body = null;
  try {
    body = await response.json();
  } catch (_) {
    body = null;
  }
  if (!response.ok) {
    let detail = body?.detail;
    if (Array.isArray(detail)) {
      detail = detail.map((item) => item.msg).join("; ");
    }
    const error = new Error(detail || `Request failed with status ${response.status}`);
    error.status = response.status;
    throw error;
  }
  return body;
}

async function checkHealth() {
  try {
    await apiRequest("/health");
    setApiStatus(true);
  } catch (_) {
    setApiStatus(false);
  }
}

async function checkAuthSession() {
  if (!state.token) {
    resetApplicationViewState();
    updateAuthUI();
    openAuth("login", false);
    return;
  }
  try {
    const user = await apiRequest("/auth/me");
    state.user = user;
    localStorage.setItem("generic-ml-user", JSON.stringify(user));
    updateAuthUI();
    closeAuth();
    if (state.view === "dashboard") loadDashboardStats();
  } catch (_) {
    resetApplicationViewState();
    localStorage.removeItem("generic-ml-token");
    localStorage.removeItem("generic-ml-user");
    updateAuthUI();
    openAuth("login", false);
  }
}

function setView(view) {
  state.view = view;
  $$(".view").forEach((section) => section.classList.toggle("is-visible", section.id === `view-${view}`));
  $$(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.view === view));
  if ($("#page-label")) {
    const labels = {
      dashboard: "Dashboard",
      detect: "Run Detection",
      files: "File Repository",
      logs: "System Logs",
      profile: "My Profile",
      predict: "Prediction Studio",
      admin: "Admin Users",
    };
    $("#page-label").textContent = labels[view] || view.charAt(0).toUpperCase() + view.slice(1);
  }
  $(".app-shell").classList.remove("sidebar-open");
  if (view === "dashboard" && state.user) loadDashboardStats();
  if (view === "files") loadFiles();
  if (view === "logs") loadLogs(1);
  if (view === "admin") loadUsers();
  if (view === "profile") renderProfile();
}

function updateAuthUI() {
  const authenticated = Boolean(state.user);
  if ($("#auth-button")) {
    $("#auth-button").classList.toggle("is-hidden", authenticated);
    $("#auth-button").textContent = authenticated ? state.user.username : "Sign in";
  }
  if ($("#principal-badge")) {
    $("#principal-badge").classList.toggle("is-hidden", !authenticated);
  }
  if ($("#principal-username") && state.user) {
    $("#principal-username").textContent = state.user.username;
  }
  if ($("#topbar-logout-button")) {
    $("#topbar-logout-button").classList.toggle("is-hidden", !authenticated);
  }
  if ($("#logout-button")) {
    $("#logout-button").classList.toggle("is-hidden", !authenticated);
  }
  $$(".admin-only").forEach((item) => item.classList.toggle("is-hidden", state.user?.role !== "ADMIN"));
  renderProfile();
}

async function loadDashboardStats() {
  if (!state.user) return;
  const loading = $("#recent-preds-loading");
  if (loading) loading.classList.remove("is-hidden");
  try {
    const stats = await apiRequest("/ml/stats");
    state.dashboardStats = stats;
    renderDashboardStats(stats);
  } catch (error) {
    showToast("Unable to load dashboard data.", "error");
  } finally {
    if (loading) loading.classList.add("is-hidden");
  }
}

function renderDashboardStats(stats) {
  if (!stats) return;

  if ($("#dash-total-inferences")) {
    $("#dash-total-inferences").textContent = stats.total_inferences;
  }
  if ($("#dash-avg-confidence")) {
    $("#dash-avg-confidence").textContent =
      stats.average_confidence !== null ? `${stats.average_confidence}%` : "N/A";
  }
  if ($("#dash-storage-quota")) {
    $("#dash-storage-quota").textContent =
      stats.storage_bytes !== null ? `${stats.storage_bytes} B` : "N/A";
  }

  const predsTable = $("#recent-preds-table");
  const predsEmpty = $("#recent-preds-empty");
  const predsBody = $("#recent-preds-body");

  if (stats.recent_predictions && stats.recent_predictions.length > 0) {
    if (predsTable) predsTable.classList.remove("is-hidden");
    if (predsEmpty) predsEmpty.classList.add("is-hidden");
    if (predsBody) {
      predsBody.innerHTML = stats.recent_predictions
        .map((p) => {
          const dateStr = p.created_at ? new Date(p.created_at).toLocaleString() : "N/A";
          let labelStr = "Output: " + escapeHtml(JSON.stringify(p.prediction_value));
          let inputType = "Tabular";
          let confStr = "N/A";

          if (typeof p.prediction_value === "object" && p.prediction_value !== null && p.prediction_value.detections) {
            inputType = "Image";
            const count = p.prediction_value.detection_count || 0;
            labelStr = `Image Detection (${count} objects)`;
            if (p.prediction_value.detections.length > 0) {
              const maxConf = Math.max(...p.prediction_value.detections.map((d) => d.confidence || 0));
              confStr = `${(maxConf * 100).toFixed(1)}%`;
            }
          }

          return `
            <tr>
              <td class="user-id">#${p.id}</td>
              <td class="user-name"><strong>${labelStr}</strong></td>
              <td><span class="role-chip">${confStr}</span></td>
              <td>${inputType}</td>
              <td style="font-size:12px; color:var(--muted);">${dateStr}</td>
              <td><button class="small-button" data-view-target="${inputType === 'Image' ? 'detect' : 'predict'}">View Report</button></td>
            </tr>`;
        })
        .join("");
    }
  } else {
    if (predsTable) predsTable.classList.add("is-hidden");
    if (predsEmpty) predsEmpty.classList.remove("is-hidden");
  }

  const summaryEmpty = $("#class-summary-empty");
  const summaryList = $("#class-summary-list");
  const summaryKeys = Object.keys(stats.classification_summary || {});

  if (summaryKeys.length > 0) {
    if (summaryEmpty) summaryEmpty.classList.add("is-hidden");
    if (summaryList) {
      summaryList.classList.remove("is-hidden");
      summaryList.innerHTML = summaryKeys
        .map((key) => {
          const count = stats.classification_summary[key];
          return `
            <div class="summary-row">
              <span>Output Class: ${escapeHtml(key)}</span>
              <span class="summary-count-chip">${count}</span>
            </div>`;
        })
        .join("");
    }
  } else {
    if (summaryEmpty) summaryEmpty.classList.remove("is-hidden");
    if (summaryList) summaryList.classList.add("is-hidden");
  }

  const auditEmpty = $("#audit-timeline-empty");
  const auditList = $("#audit-timeline-list");

  if (stats.audit_timeline && stats.audit_timeline.length > 0) {
    if (auditEmpty) auditEmpty.classList.add("is-hidden");
    if (auditList) {
      auditList.classList.remove("is-hidden");
      auditList.innerHTML = stats.audit_timeline
        .map((a) => {
          const timeStr = a.timestamp
            ? new Date(a.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
            : "";
          return `
            <div class="audit-item-row">
              <div class="audit-action-title">
                <span>${escapeHtml(a.action_category)}</span>
                <span class="audit-meta-text">${timeStr}</span>
              </div>
              <div class="audit-meta-text">IP: ${escapeHtml(a.source_ip || "127.0.0.1")}</div>
              <div class="audit-desc-text">${escapeHtml(a.transaction_details || "")}</div>
            </div>`;
        })
        .join("");
    }
  } else {
    if (auditEmpty) auditEmpty.classList.remove("is-hidden");
    if (auditList) auditList.classList.add("is-hidden");
  }
}

function handleFileSelect(file) {
  if (!file) return;
  const ext = file.name.split(".").pop().toLowerCase();
  const allowedExts = ["png", "jpg", "jpeg", "webp"];

  if (!allowedExts.includes(ext)) {
    showToast("Invalid file format. Please upload PNG, JPG, JPEG, or WEBP.", "error");
    return;
  }

  if (file.size > 10 * 1024 * 1024) {
    showToast("File is too large. Maximum allowed size is 10MB.", "error");
    return;
  }

  state.selectedImageFile = file;
  $("#image-preview-name").textContent = file.name;
  $("#image-preview-size").textContent = `${(file.size / 1024).toFixed(1)} KB`;

  const reader = new FileReader();
  reader.onload = (e) => {
    $("#image-preview-img").src = e.target.result;
    $("#image-preview-card").classList.remove("is-hidden");
    $("#run-detect-btn").disabled = false;
    $("#detect-error").classList.add("is-hidden");
  };
  reader.readAsDataURL(file);
}

function clearSelectedImage() {
  state.selectedImageFile = null;
  if ($("#image-file-input")) $("#image-file-input").value = "";
  if ($("#image-preview-card")) $("#image-preview-card").classList.add("is-hidden");
  if ($("#run-detect-btn")) $("#run-detect-btn").disabled = true;
  if ($("#detect-error")) $("#detect-error").classList.add("is-hidden");
}

async function runObjectDetection() {
  if (!state.selectedImageFile) {
    showToast("Please select an image file first.", "error");
    return;
  }

  const errorBox = $("#detect-error");
  const button = $("#run-detect-btn");
  const stateChip = $("#detect-state");

  errorBox.classList.add("is-hidden");
  button.disabled = true;
  button.innerHTML = "Running Inference Pipeline... <span>↻</span>";
  if (stateChip) stateChip.textContent = "Running";

  const formData = new FormData();
  formData.append("file", state.selectedImageFile);

  try {
    const headers = {};
    if (state.token) {
      headers["Authorization"] = `Bearer ${state.token}`;
    }
    const response = await fetch("/ml/detect", {
      method: "POST",
      headers,
      body: formData,
    });

    let body = null;
    try {
      body = await response.json();
    } catch (_) {}

    if (!response.ok) {
      let detail = body?.detail || `Inference failed with status ${response.status}`;
      throw new Error(detail);
    }

    renderDetectionResult(body);
    if (stateChip) stateChip.textContent = "Complete";
    showToast(`Object detection complete! Found ${body.detection_count} object(s).`, "success");
    loadDashboardStats();
  } catch (error) {
    if (stateChip) stateChip.textContent = "Error";
    errorBox.textContent = error.message;
    errorBox.classList.remove("is-hidden");
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    button.innerHTML = "RUN INFERENCE PIPELINE <span>→</span>";
  }
}

function renderDetectionResult(result) {
  $("#detect-empty").classList.add("is-hidden");
  $("#detect-result-content").classList.remove("is-hidden");

  $("#detect-model-name").textContent = result.model_identifier || "ssdlite320_mobilenet_v3_large";
  $("#detect-count-text").textContent = result.detection_count;
  $("#detect-orig-img").src = result.original_image_url;
  $("#detect-annotated-img").src = result.annotated_image_url;
  $("#detect-pred-id").textContent = `#${result.prediction_id}`;
  $("#detect-timestamp").textContent = result.created_at ? new Date(result.created_at).toLocaleString() : "Just now";

  const zeroState = $("#detect-zero-state");
  const detTable = $("#detections-table");
  const detBody = $("#detections-body");

  if (result.detections && result.detections.length > 0) {
    zeroState.classList.add("is-hidden");
    detTable.classList.remove("is-hidden");
    detBody.innerHTML = result.detections
      .map((d) => {
        const confPct = (d.confidence * 100).toFixed(1);
        const bboxStr = `(${d.bbox.x1}, ${d.bbox.y1}, ${d.bbox.x2}, ${d.bbox.y2})`;
        return `
          <tr>
            <td class="user-name"><strong>${escapeHtml(d.class_name)}</strong></td>
            <td><span class="role-chip">${confPct}%</span></td>
            <td style="font-family:monospace; font-size:11px; color:var(--muted);">${bboxStr}</td>
          </tr>`;
      })
      .join("");
  } else {
    zeroState.classList.remove("is-hidden");
    detTable.classList.add("is-hidden");
    detBody.innerHTML = "";
  }
}

function openAuth(mode = "login", allowClose = true) {
  state.authMode = mode;
  $("#auth-modal").classList.remove("is-hidden");

  const closeBtn = $("#close-modal");
  if (closeBtn) {
    closeBtn.style.display = allowClose || Boolean(state.user) ? "block" : "none";
  }

  const isRegister = mode === "register";
  $("#username-field").classList.toggle("is-hidden", !isRegister);
  $("#confirm-password-field").classList.toggle("is-hidden", !isRegister);
  $("#login-tab").classList.toggle("is-active", !isRegister);
  $("#register-tab").classList.toggle("is-active", isRegister);

  if ($("#auth-title")) {
    $("#auth-title").textContent = isRegister ? "Create your account" : "Welcome back";
  }
  if ($("#auth-subtitle")) {
    $("#auth-subtitle").textContent = isRegister
      ? "Create an account through the existing backend."
      : "Sign in with your existing account.";
  }
  if ($("#auth-email-label")) {
    $("#auth-email-label").textContent = isRegister ? "Email" : "Username or Email";
  }
  if ($("#auth-email")) {
    $("#auth-email").placeholder = isRegister ? "name@example.com" : "Enter email or username";
  }
  if ($("#auth-submit")) {
    $("#auth-submit").textContent = isRegister ? "Create Account" : "Sign In";
  }
  if ($("#auth-toggle-text")) {
    $("#auth-toggle-text").textContent = isRegister ? "Already have an account?" : "Don't have an account?";
  }
  if ($("#auth-toggle-btn")) {
    $("#auth-toggle-btn").textContent = isRegister ? "Sign In" : "Create Account";
  }

  $("#auth-error").classList.add("is-hidden");
  $("#auth-form").reset();

  if (isRegister) {
    $("#auth-username").focus();
  } else {
    $("#auth-email").focus();
  }
}

function closeAuth() {
  if (state.user) {
    $("#auth-modal").classList.add("is-hidden");
  }
}

function validateAuthForm(mode, username, email, password, confirmPassword) {
  if (mode === "register") {
    if (!username) return "Username is required.";
    if (!email) return "Email is required.";
    if (!email.includes("@") || !email.includes(".")) return "Please enter a valid email address.";
    if (!password) return "Password is required.";
    if (password.length < 6) return "Password must be at least 6 characters long.";
    if (password !== confirmPassword) return "Passwords do not match.";
  } else {
    if (!email) return "Please enter your username or email.";
    if (!password) return "Please enter your password.";
  }
  return null;
}

function resetApplicationViewState() {
  state.user = null;
  state.token = null;
  state.dashboardStats = null;
  state.users = [];
  state.logsState = { page: 1, limit: 20, pages: 1, total: 0 };

  clearSelectedImage();

  // Reset Detection View DOM
  if ($("#detect-result-content")) $("#detect-result-content").classList.add("is-hidden");
  if ($("#detect-empty")) $("#detect-empty").classList.remove("is-hidden");
  if ($("#detect-state")) $("#detect-state").textContent = "Waiting";
  if ($("#detect-model-name")) $("#detect-model-name").textContent = "ssdlite320_mobilenet_v3_large";
  if ($("#detect-count-text")) $("#detect-count-text").textContent = "0";
  if ($("#detect-orig-img")) $("#detect-orig-img").src = "";
  if ($("#detect-annotated-img")) $("#detect-annotated-img").src = "";
  if ($("#detect-pred-id")) $("#detect-pred-id").textContent = "#0";
  if ($("#detect-timestamp")) $("#detect-timestamp").textContent = "N/A";
  if ($("#detections-table")) $("#detections-table").classList.add("is-hidden");
  if ($("#detect-zero-state")) $("#detect-zero-state").classList.add("is-hidden");
  if ($("#detections-body")) $("#detections-body").innerHTML = "";

  // Reset Tabular Prediction View DOM
  if ($("#prediction-result")) $("#prediction-result").classList.add("is-hidden");
  if ($("#prediction-empty")) $("#prediction-empty").classList.remove("is-hidden");
  if ($("#result-state")) $("#result-state").textContent = "Waiting";
  if ($("#prediction-value")) $("#prediction-value").textContent = "";
  if ($("#probability-block")) $("#probability-block").classList.add("is-hidden");
  if ($("#probability-value")) $("#probability-value").textContent = "";

  // Reset Dashboard View DOM
  if ($("#dash-total-inferences")) $("#dash-total-inferences").textContent = "0";
  if ($("#dash-avg-confidence")) $("#dash-avg-confidence").textContent = "N/A";
  if ($("#dash-storage-quota")) $("#dash-storage-quota").textContent = "N/A";
  if ($("#recent-preds-body")) $("#recent-preds-body").innerHTML = "";
  if ($("#recent-preds-table")) $("#recent-preds-table").classList.add("is-hidden");
  if ($("#recent-preds-empty")) $("#recent-preds-empty").classList.remove("is-hidden");
  if ($("#class-summary-list")) $("#class-summary-list").innerHTML = "";
  if ($("#class-summary-list")) $("#class-summary-list").classList.add("is-hidden");
  if ($("#class-summary-empty")) $("#class-summary-empty").classList.remove("is-hidden");
  if ($("#audit-timeline-list")) $("#audit-timeline-list").innerHTML = "";
  if ($("#audit-timeline-list")) $("#audit-timeline-list").classList.add("is-hidden");
  if ($("#audit-timeline-empty")) $("#audit-timeline-empty").classList.remove("is-hidden");

  // Reset Files Repository View DOM
  if ($("#files-body")) $("#files-body").innerHTML = "";
  if ($("#files-table")) $("#files-table").classList.add("is-hidden");
  if ($("#files-empty")) $("#files-empty").classList.remove("is-hidden");

  // Reset System Logs View DOM
  if ($("#logs-body")) $("#logs-body").innerHTML = "";
  if ($("#logs-table")) $("#logs-table").classList.add("is-hidden");
  if ($("#logs-pagination")) $("#logs-pagination").classList.add("is-hidden");
  if ($("#logs-empty")) $("#logs-empty").classList.remove("is-hidden");

  // Reset Admin View DOM
  if ($("#users-body")) $("#users-body").innerHTML = "";
  if ($("#users-table")) $("#users-table").classList.add("is-hidden");
  if ($("#users-empty")) $("#users-empty").classList.remove("is-hidden");
}

async function submitAuth(event) {
  event.preventDefault();
  const submit = $("#auth-submit");
  const errorBox = $("#auth-error");

  const email = $("#auth-email").value.trim();
  const password = $("#auth-password").value;
  const username = $("#auth-username").value.trim();
  const confirmPassword = $("#auth-confirm-password").value;

  const validationError = validateAuthForm(state.authMode, username, email, password, confirmPassword);
  if (validationError) {
    errorBox.textContent = validationError;
    errorBox.classList.remove("is-hidden");
    return;
  }

  submit.disabled = true;
  submit.textContent = state.authMode === "login" ? "Signing in..." : "Creating account...";
  errorBox.classList.add("is-hidden");

  try {
    let payload;
    let endpoint;
    if (state.authMode === "login") {
      endpoint = "/auth/login";
      payload = email.includes("@") ? { email, password } : { username: email, password };
    } else {
      endpoint = "/auth/register";
      payload = { username, email, password };
    }

    const responseData = await apiRequest(endpoint, {
      method: "POST",
      body: JSON.stringify(payload),
    });

    resetApplicationViewState();
    state.user = responseData;
    if (responseData.session_token) {
      state.token = responseData.session_token;
      localStorage.setItem("generic-ml-token", responseData.session_token);
    }
    localStorage.setItem("generic-ml-user", JSON.stringify(responseData));

    updateAuthUI();
    closeAuth();
    loadDashboardStats();
    showToast(state.authMode === "login" ? "Signed in successfully." : "Account created successfully.", "success");
  } catch (error) {
    let message = error.message || "An error occurred during authentication.";
    if (message.includes("401") || message.toLowerCase().includes("invalid")) {
      message = "Invalid credentials. Please check your username/email and password.";
    } else if (message.includes("409") || message.toLowerCase().includes("duplicate")) {
      message = "Username or email is already registered.";
    } else if (message.toLowerCase().includes("failed to fetch")) {
      message = "Unable to connect to server. Please try again later.";
    }
    errorBox.textContent = message;
    errorBox.classList.remove("is-hidden");
  } finally {
    submit.disabled = false;
    submit.textContent = state.authMode === "login" ? "Sign In" : "Create Account";
  }
}

async function handleLogout() {
  try {
    await apiRequest("/auth/logout", { method: "POST" });
  } catch (_) {
    // Ignore backend logout network errors
  }
  resetApplicationViewState();
  localStorage.removeItem("generic-ml-token");
  localStorage.removeItem("generic-ml-user");
  updateAuthUI();
  setView("dashboard");
  openAuth("login", false);
  showToast("Signed out.", "success");
}

function renderProfile() {
  const panel = $("#profile-panel");
  if (!panel) return;
  if (!state.user) {
    panel.innerHTML = `
      <div class="empty-state">
        <div class="empty-mark">?</div>
        <h3>No authenticated user</h3>
        <p>Sign in to display the user information available from the backend.</p>
        <button class="button button-dark" data-auth-action="login">Sign in</button>
      </div>`;
    return;
  }

  const createdStr = state.user.created_at ? new Date(state.user.created_at).toLocaleString() : "N/A";
  const lastLoginStr = state.user.last_login ? new Date(state.user.last_login).toLocaleString() : "First Session";

  panel.innerHTML = `
    <div class="profile-header">
      <div class="avatar">${escapeHtml(state.user.username.slice(0, 1).toUpperCase())}</div>
      <div>
        <p class="eyebrow">AUTHENTICATED USER / PRINCIPAL</p>
        <h2>${escapeHtml(state.user.username)}</h2>
        <p class="section-copy">${escapeHtml(state.user.email)}</p>
      </div>
    </div>

    <div class="result-meta" style="margin-top:20px; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));">
      <div><span>User ID</span><strong>#${state.user.id}</strong></div>
      <div><span>Role</span><strong style="color:var(--accent);">${escapeHtml(state.user.role)}</strong></div>
      <div><span>Status</span><strong style="color:#10b981;">${state.user.is_active ? "Active" : "Inactive"}</strong></div>
      <div><span>Account Created</span><strong>${createdStr}</strong></div>
      <div><span>Last Login</span><strong>${lastLoginStr}</strong></div>
    </div>

    <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:24px; margin-top:28px;">
      <!-- Edit Profile Card -->
      <div style="background:#161920; border:1px solid #2d323e; border-radius:10px; padding:20px;">
        <h3 style="font-size:16px; margin-bottom:6px; color:#f3f4f6;">Edit Profile</h3>
        <p class="section-copy" style="font-size:12px; margin-bottom:16px;">Update your account username or email address.</p>

        <form id="edit-profile-form">
          <div class="field-group" style="margin-bottom:14px;">
            <label class="field-label" for="edit-profile-username">Username</label>
            <input id="edit-profile-username" class="text-input" value="${escapeHtml(state.user.username)}" required />
          </div>
          <div class="field-group" style="margin-bottom:14px;">
            <label class="field-label" for="edit-profile-email">Email Address</label>
            <input id="edit-profile-email" type="email" class="text-input" value="${escapeHtml(state.user.email)}" required />
          </div>
          <p id="edit-profile-error" class="field-error is-hidden" style="margin-bottom:12px;"></p>
          <button id="edit-profile-submit" class="button button-accent button-wide" type="submit">Update Profile</button>
        </form>
      </div>

      <!-- Change Password Card -->
      <div style="background:#161920; border:1px solid #2d323e; border-radius:10px; padding:20px;">
        <h3 style="font-size:16px; margin-bottom:6px; color:#f3f4f6;">Change Password</h3>
        <p class="section-copy" style="font-size:12px; margin-bottom:16px;">Security credentials change requires current password verification.</p>

        <form id="change-pass-form">
          <div class="field-group" style="margin-bottom:14px;">
            <label class="field-label" for="change-pass-current">Current Password</label>
            <input id="change-pass-current" type="password" class="text-input" placeholder="••••••••" required />
          </div>
          <div class="field-group" style="margin-bottom:14px;">
            <label class="field-label" for="change-pass-new">New Password</label>
            <input id="change-pass-new" type="password" class="text-input" placeholder="Min 6 characters" required />
          </div>
          <div class="field-group" style="margin-bottom:14px;">
            <label class="field-label" for="change-pass-confirm">Confirm New Password</label>
            <input id="change-pass-confirm" type="password" class="text-input" placeholder="Repeat new password" required />
          </div>
          <p id="change-pass-error" class="field-error is-hidden" style="margin-bottom:12px;"></p>
          <button id="change-pass-submit" class="button button-accent button-wide" type="submit">Change Password</button>
        </form>
      </div>
    </div>
  `;
}

async function handleEditProfileSubmit(event) {
  event.preventDefault();
  const username = $("#edit-profile-username")?.value.trim();
  const email = $("#edit-profile-email")?.value.trim();
  const errorBox = $("#edit-profile-error");
  const submitBtn = $("#edit-profile-submit");

  if (!username || !email) {
    if (errorBox) {
      errorBox.textContent = "Username and email are required.";
      errorBox.classList.remove("is-hidden");
    }
    return;
  }

  if (submitBtn) submitBtn.disabled = true;
  if (errorBox) errorBox.classList.add("is-hidden");

  try {
    const updatedUser = await apiRequest("/auth/profile", {
      method: "PUT",
      body: JSON.stringify({ username, email }),
    });

    state.user = updatedUser;
    localStorage.setItem("generic-ml-user", JSON.stringify(updatedUser));
    updateAuthUI();
    showToast("Profile updated successfully.", "success");
  } catch (error) {
    if (errorBox) {
      errorBox.textContent = error.message || "Failed to update profile.";
      errorBox.classList.remove("is-hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function handleChangePasswordSubmit(event) {
  event.preventDefault();
  const current_password = $("#change-pass-current")?.value;
  const new_password = $("#change-pass-new")?.value;
  const confirm_new_password = $("#change-pass-confirm")?.value;
  const errorBox = $("#change-pass-error");
  const submitBtn = $("#change-pass-submit");

  if (!current_password || !new_password || !confirm_new_password) {
    if (errorBox) {
      errorBox.textContent = "All password fields are required.";
      errorBox.classList.remove("is-hidden");
    }
    return;
  }

  if (new_password.length < 6) {
    if (errorBox) {
      errorBox.textContent = "New password must be at least 6 characters long.";
      errorBox.classList.remove("is-hidden");
    }
    return;
  }

  if (new_password !== confirm_new_password) {
    if (errorBox) {
      errorBox.textContent = "New passwords do not match.";
      errorBox.classList.remove("is-hidden");
    }
    return;
  }

  if (submitBtn) submitBtn.disabled = true;
  if (errorBox) errorBox.classList.add("is-hidden");

  try {
    const response = await apiRequest("/auth/change-password", {
      method: "POST",
      body: JSON.stringify({
        current_password,
        new_password,
        confirm_new_password,
      }),
    });

    if (response.session_token) {
      state.token = response.session_token;
      localStorage.setItem("generic-ml-token", response.session_token);
    }
    state.user = response;
    localStorage.setItem("generic-ml-user", JSON.stringify(response));
    updateAuthUI();
    showToast("Password changed successfully.", "success");
    if ($("#change-pass-form")) $("#change-pass-form").reset();
  } catch (error) {
    if (errorBox) {
      errorBox.textContent = error.message || "Failed to change password.";
      errorBox.classList.remove("is-hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "'": "&#39;",
    '"': "&quot;",
  })[char]);
}

function formatValue(value) {
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

async function runPrediction() {
  const button = $("#predict-button");
  const errorBox = $("#features-error");
  let features;
  try {
    features = JSON.parse($("#features-input").value);
    if (!features || Array.isArray(features) || typeof features !== "object" || Object.keys(features).length === 0) {
      throw new Error("Enter a non-empty JSON object of feature values.");
    }
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove("is-hidden");
    return;
  }
  errorBox.classList.add("is-hidden");
  button.disabled = true;
  button.innerHTML = "Predicting...";
  $("#result-state").textContent = "Running";
  try {
    const result = await apiRequest("/ml/predict", { method: "POST", body: JSON.stringify({ features }) });
    $("#prediction-empty").classList.add("is-hidden");
    $("#prediction-result").classList.remove("is-hidden");
    $("#prediction-value").textContent = formatValue(result.prediction);
    const probability = result.probabilities;
    const hasProbability = probability !== null && probability !== undefined;
    $("#probability-block").classList.toggle("is-hidden", !hasProbability);
    if (hasProbability) $("#probability-value").textContent = formatValue(probability);
    $("#result-state").textContent = "Complete";
    showToast("Prediction completed and persisted.", "success");
    loadDashboardStats();
  } catch (error) {
    $("#result-state").textContent = "Error";
    showToast(error.message, "error");
  } finally {
    button.disabled = false;
    button.innerHTML = "Run prediction <span>→</span>";
  }
}

async function loadUsers() {
  if (state.user?.role !== "ADMIN") {
    $("#users-body").innerHTML = "";
    $("#users-empty").classList.remove("is-hidden");
    $("#users-empty").querySelector("h3").textContent = "Admin access required";
    return;
  }
  $("#users-loading").classList.remove("is-hidden");
  $("#users-empty").classList.add("is-hidden");
  try {
    state.users = await apiRequest("/admin/users");
    renderUsers();
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    $("#users-loading").classList.add("is-hidden");
  }
}

function renderUsers() {
  const body = $("#users-body");
  $("#users-empty").classList.toggle("is-hidden", state.users.length !== 0);
  body.innerHTML = state.users
    .map(
      (user) => `
    <tr>
      <td class="user-id">#${user.id}</td>
      <td class="user-name">${escapeHtml(user.username)}</td>
      <td>${escapeHtml(user.email)}</td>
      <td><span class="role-chip">${escapeHtml(user.role)}</span></td>
      <td><span class="status-chip ${user.is_active ? "" : "inactive"}">${user.is_active ? "Active" : "Inactive"}</span></td>
      <td>
        <div class="table-actions">
          <button class="small-button" data-user-action="toggle" data-user-id="${user.id}" data-active="${user.is_active}">
            ${user.is_active ? "Deactivate" : "Activate"}
          </button>
          <button class="small-button" data-user-action="role" data-user-id="${user.id}">Change role</button>
        </div>
      </td>
    </tr>`
    )
    .join("");
}

async function loadFiles() {
  if (!state.user) {
    const filesBody = $("#files-body");
    const filesEmpty = $("#files-empty");
    const filesTable = $("#files-table");
    if (filesBody) filesBody.innerHTML = "";
    if (filesTable) filesTable.classList.add("is-hidden");
    if (filesEmpty) {
      filesEmpty.classList.remove("is-hidden");
      const h3 = filesEmpty.querySelector("h3");
      if (h3) h3.textContent = "Authentication required";
    }
    return;
  }

  const loading = $("#files-loading");
  const empty = $("#files-empty");
  const table = $("#files-table");

  if (loading) loading.classList.remove("is-hidden");
  if (empty) empty.classList.add("is-hidden");
  if (table) table.classList.add("is-hidden");

  try {
    const files = await apiRequest("/files");
    renderFiles(files);
  } catch (error) {
    showToast(error.message || "Failed to load files.", "error");
    if (empty) {
      empty.classList.remove("is-hidden");
      const h3 = empty.querySelector("h3");
      if (h3) h3.textContent = "Error loading files";
    }
  } finally {
    if (loading) loading.classList.add("is-hidden");
  }
}

function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function renderFiles(files) {
  const table = $("#files-table");
  const empty = $("#files-empty");
  const body = $("#files-body");

  if (!files || files.length === 0) {
    if (table) table.classList.add("is-hidden");
    if (empty) {
      empty.classList.remove("is-hidden");
      const h3 = empty.querySelector("h3");
      if (h3) h3.textContent = "No files stored";
    }
    if (body) body.innerHTML = "";
    return;
  }

  if (empty) empty.classList.add("is-hidden");
  if (table) table.classList.remove("is-hidden");

  if (body) {
    body.innerHTML = files
      .map((f) => {
        const dateStr = f.created_at ? new Date(f.created_at).toLocaleString() : "N/A";
        const sizeStr = formatFileSize(f.file_size_bytes || 0);
        const predStr = f.prediction_id ? `#${f.prediction_id}` : "None";
        const categoryLabel = f.category === "original_image" ? "Original Image" :
                              f.category === "annotated_image" ? "Annotated Image" :
                              f.category;
        
        return `
          <tr>
            <td class="user-id">#${f.id}</td>
            <td class="user-name"><strong>${escapeHtml(f.original_name || f.filename)}</strong></td>
            <td><span class="role-chip">${escapeHtml(categoryLabel)}</span></td>
            <td style="font-size:12px; color:var(--muted);">${escapeHtml(f.file_type)}</td>
            <td>${sizeStr}</td>
            <td style="font-size:12px; color:var(--muted);">${dateStr}</td>
            <td>${predStr !== "None" ? `<span class="role-chip">${predStr}</span>` : '<span style="color:var(--muted)">None</span>'}</td>
            <td>
              <div class="table-actions">
                <a href="${f.download_url}?disposition=inline" target="_blank" class="small-button" style="text-decoration:none;">View</a>
                <a href="${f.download_url}" download="${escapeHtml(f.original_name)}" class="small-button" style="text-decoration:none;">Download</a>
                <button class="small-button button-danger" data-file-action="delete" data-file-id="${f.id}" data-file-name="${escapeHtml(f.original_name)}">Delete</button>
              </div>
            </td>
          </tr>`;
      })
      .join("");
  }
}

async function loadLogs(page = 1) {
  if (!state.user) {
    const logsEmpty = $("#logs-empty");
    const logsTable = $("#logs-table");
    const logsPagination = $("#logs-pagination");
    if (logsTable) logsTable.classList.add("is-hidden");
    if (logsPagination) logsPagination.classList.add("is-hidden");
    if (logsEmpty) {
      logsEmpty.classList.remove("is-hidden");
      const h3 = logsEmpty.querySelector("h3");
      if (h3) h3.textContent = "Authentication required";
    }
    return;
  }

  const loading = $("#logs-loading");
  const empty = $("#logs-empty");
  const table = $("#logs-table");
  const pagination = $("#logs-pagination");

  if (loading) loading.classList.remove("is-hidden");
  if (empty) empty.classList.add("is-hidden");
  if (table) table.classList.add("is-hidden");
  if (pagination) pagination.classList.add("is-hidden");

  state.logsState.page = page;

  const actionFilter = $("#logs-filter-action")?.value || "";
  const userFilter = $("#logs-filter-username")?.value || "";
  const startFilter = $("#logs-filter-start")?.value || "";
  const endFilter = $("#logs-filter-end")?.value || "";

  const queryParams = new URLSearchParams({
    page: String(page),
    limit: String(state.logsState.limit),
  });

  if (actionFilter) queryParams.set("action", actionFilter);
  if (userFilter && state.user?.role === "ADMIN") queryParams.set("username", userFilter);
  if (startFilter) queryParams.set("start_date", startFilter);
  if (endFilter) queryParams.set("end_date", endFilter);

  try {
    const data = await apiRequest(`/audit-logs?${queryParams.toString()}`);
    renderLogs(data);
  } catch (error) {
    showToast(error.message || "Failed to load audit logs.", "error");
    if (empty) {
      empty.classList.remove("is-hidden");
      const h3 = empty.querySelector("h3");
      if (h3) h3.textContent = "Error loading audit logs";
    }
  } finally {
    if (loading) loading.classList.add("is-hidden");
  }
}

function renderLogs(data) {
  const table = $("#logs-table");
  const empty = $("#logs-empty");
  const body = $("#logs-body");
  const pagination = $("#logs-pagination");
  const pageInfo = $("#logs-page-info");
  const prevBtn = $("#logs-prev-page");
  const nextBtn = $("#logs-next-page");
  const totalCount = $("#logs-total-count");

  if (!data || !data.items || data.items.length === 0) {
    if (table) table.classList.add("is-hidden");
    if (pagination) pagination.classList.add("is-hidden");
    if (empty) {
      empty.classList.remove("is-hidden");
      const h3 = empty.querySelector("h3");
      if (h3) h3.textContent = "No audit activity found.";
    }
    if (body) body.innerHTML = "";
    if (totalCount) totalCount.textContent = "0 log entries";
    return;
  }

  state.logsState.page = data.page;
  state.logsState.pages = data.pages;
  state.logsState.total = data.total;

  if (empty) empty.classList.add("is-hidden");
  if (table) table.classList.remove("is-hidden");
  if (pagination) pagination.classList.remove("is-hidden");

  if (totalCount) totalCount.textContent = `${data.total} log entries`;
  if (pageInfo) pageInfo.textContent = `Page ${data.page} of ${data.pages}`;

  if (prevBtn) prevBtn.disabled = data.page <= 1;
  if (nextBtn) nextBtn.disabled = data.page >= data.pages;

  if (body) {
    body.innerHTML = data.items
      .map((item) => {
        const timeStr = item.timestamp ? new Date(item.timestamp).toLocaleString() : "N/A";
        const usernameStr = item.username || (item.user_id ? `#${item.user_id}` : "Anonymous");
        const detailsStr = item.transaction_details || "";

        return `
          <tr>
            <td class="user-id">#${item.id}</td>
            <td style="font-size:12px; color:var(--muted);">${timeStr}</td>
            <td class="user-name"><strong>${escapeHtml(usernameStr)}</strong></td>
            <td><span class="role-chip">${escapeHtml(item.action_category)}</span></td>
            <td style="font-size:12px; color:var(--muted);">${escapeHtml(item.source_ip || "127.0.0.1")}</td>
            <td style="font-size:12px; max-width:300px; word-break:break-word;">${escapeHtml(detailsStr)}</td>
          </tr>`;
      })
      .join("");
  }
}

async function updateUser(userId, action, active) {
  if (!window.confirm(action === "role" ? "Change this user's role?" : `${active ? "Deactivate" : "Activate"} this user?`)) return;
  let path;
  let body;
  if (action === "role") {
    const role = window.prompt("Enter USER or ADMIN:", "USER");
    if (!["USER", "ADMIN"].includes(role)) {
      showToast("Role must be USER or ADMIN.", "error");
      return;
    }
    path = `/admin/users/${userId}/role`;
    body = { role };
  } else {
    path = `/admin/users/${userId}/${active ? "deactivate" : "activate"}`;
  }
  try {
    await apiRequest(path, { method: "PATCH", ...(body ? { body: JSON.stringify(body) } : {}) });
    showToast("User updated successfully.", "success");
    await loadUsers();
  } catch (error) {
    showToast(error.message, "error");
  }
}

function initialize() {
  checkHealth();
  checkAuthSession();

  $$(".nav-item").forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));
  document.addEventListener("click", (event) => {
    const btn = event.target.closest("[data-view-target]");
    if (btn) setView(btn.dataset.viewTarget);
  });

  // Dropzone & File Input Listeners
  const dropzone = $("#image-dropzone");
  const fileInput = $("#image-file-input");
  const browseBtn = $("#browse-files-btn");
  const clearBtn = $("#clear-image-btn");
  const runDetectBtn = $("#run-detect-btn");

  if (browseBtn && fileInput) {
    browseBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileSelect(e.target.files[0]);
      }
    });

    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.add("drag-over");
      });
    });

    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropzone.classList.remove("drag-over");
      });
    });

    dropzone.addEventListener("drop", (e) => {
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files[0]) {
        handleFileSelect(dt.files[0]);
      }
    });
  }

  if (clearBtn) clearBtn.addEventListener("click", clearSelectedImage);
  if (runDetectBtn) runDetectBtn.addEventListener("click", runObjectDetection);

  document.addEventListener("click", (event) => {
    if (event.target.closest('[data-auth-action="login"]')) openAuth("login", true);
  });

  if ($("#auth-button")) {
    $("#auth-button").addEventListener("click", () => (state.user ? setView("profile") : openAuth("login", true)));
  }

  if ($("#topbar-logout-button")) {
    $("#topbar-logout-button").addEventListener("click", handleLogout);
  }

  if ($("#logout-button")) {
    $("#logout-button").addEventListener("click", handleLogout);
  }

  if ($("#predict-button")) $("#predict-button").addEventListener("click", runPrediction);
  if ($("#refresh-users")) $("#refresh-users").addEventListener("click", loadUsers);
  if ($("#refresh-files-btn")) $("#refresh-files-btn").addEventListener("click", loadFiles);

  if ($("#refresh-logs-btn")) $("#refresh-logs-btn").addEventListener("click", () => loadLogs(state.logsState.page));
  if ($("#logs-apply-filters")) $("#logs-apply-filters").addEventListener("click", () => loadLogs(1));
  if ($("#logs-reset-filters")) {
    $("#logs-reset-filters").addEventListener("click", () => {
      if ($("#logs-filter-action")) $("#logs-filter-action").value = "";
      if ($("#logs-filter-username")) $("#logs-filter-username").value = "";
      if ($("#logs-filter-start")) $("#logs-filter-start").value = "";
      if ($("#logs-filter-end")) $("#logs-filter-end").value = "";
      loadLogs(1);
    });
  }
  if ($("#logs-prev-page")) {
    $("#logs-prev-page").addEventListener("click", () => {
      if (state.logsState.page > 1) loadLogs(state.logsState.page - 1);
    });
  }
  if ($("#logs-next-page")) {
    $("#logs-next-page").addEventListener("click", () => {
      if (state.logsState.page < state.logsState.pages) loadLogs(state.logsState.page + 1);
    });
  }

  if ($("#files-body")) {
    $("#files-body").addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-file-action='delete']");
      if (btn) {
        const fileId = btn.dataset.fileId;
        const fileName = btn.dataset.fileName;
        if (!window.confirm(`Are you sure you want to delete file "${fileName}" (#${fileId})?`)) return;

        try {
          await apiRequest(`/files/${fileId}`, { method: "DELETE" });
          showToast(`File #${fileId} deleted successfully.`, "success");
          loadFiles();
          loadDashboardStats();
        } catch (error) {
          showToast(error.message || "Failed to delete file.", "error");
        }
      }
    });
  }

  if ($("#login-tab")) $("#login-tab").addEventListener("click", () => openAuth("login", Boolean(state.user)));
  if ($("#register-tab")) $("#register-tab").addEventListener("click", () => openAuth("register", Boolean(state.user)));
  if ($("#close-modal")) $("#close-modal").addEventListener("click", closeAuth);
  if ($("#auth-form")) $("#auth-form").addEventListener("submit", submitAuth);

  if ($("#auth-toggle-btn")) {
    $("#auth-toggle-btn").addEventListener("click", () => {
      openAuth(state.authMode === "login" ? "register" : "login", Boolean(state.user));
    });
  }

  if ($("#menu-button")) {
    $("#menu-button").addEventListener("click", () => $(".app-shell").classList.toggle("sidebar-open"));
  }

  if ($("#users-body")) {
    $("#users-body").addEventListener("click", (event) => {
      const button = event.target.closest("[data-user-action]");
      if (button) updateUser(button.dataset.userId, button.dataset.userAction, button.dataset.active === "true");
    });
  }

  document.addEventListener("submit", (event) => {
    if (event.target && event.target.id === "edit-profile-form") {
      handleEditProfileSubmit(event);
    }
    if (event.target && event.target.id === "change-pass-form") {
      handleChangePasswordSubmit(event);
    }
  });
}

document.addEventListener("DOMContentLoaded", initialize);
