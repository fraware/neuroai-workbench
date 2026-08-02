"use strict";

const reviewState = {
  health: null,
  items: [],
  activeItemId: null,
  detail: null,
  profiles: [],
  activeProfileId: localStorage.getItem("neuroai.review.profileId") || "",
  activeLeaseId: null,
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

function setText(node, value) {
  node.textContent = String(value ?? "");
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    let detail = response.statusText;
    try { detail = (await response.json()).error || detail; } catch (_) {}
    throw new Error(detail);
  }
  const type = response.headers.get("content-type") || "";
  if (type.includes("application/json")) return response.json();
  return response.blob();
}

function showToast(message, error = false) {
  const toast = $("#reviewToast");
  setText(toast, message);
  toast.className = `toast${error ? " error" : ""}`;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 6000);
}

function statusClass(value) {
  const lowered = String(value || "").toLowerCase();
  if (lowered.includes("open")) return "partial";
  if (lowered.includes("adjudicated")) return "pass";
  if (lowered.includes("stale")) return "fail";
  return "na";
}

function badge(value) {
  const span = document.createElement("span");
  span.className = `status ${statusClass(value)}`;
  setText(span, value);
  return span;
}

function renderOpsHealth(health) {
  const cards = [
    [health.plan_counts?.due ?? 0, "Due sources"],
    [health.overdue_source_count ?? 0, "Overdue sources"],
    [health.candidate_counts?.pending ?? 0, "Pending candidates"],
    [health.candidate_counts?.open_queue_items ?? 0, "Open queue items"],
  ];
  const holder = $("#opsHealthCards");
  holder.replaceChildren();
  for (const [value, label] of cards) {
    const card = document.createElement("div");
    card.className = "card";
    const v = document.createElement("div"); v.className = "value"; setText(v, value);
    const l = document.createElement("div"); l.className = "label"; setText(l, label);
    card.append(v, l);
    holder.append(card);
  }
}

function renderProfileRoleOptions(fields) {
  const roleField = (fields || []).find((field) => field.name === "roles");
  const holder = $("#profileRoles");
  holder.replaceChildren();
  for (const role of roleField?.options || []) {
    const label = document.createElement("label");
    label.className = "checkbox-inline";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "roles";
    input.value = role;
    label.append(input, document.createTextNode(` ${role}`));
    holder.append(label);
  }
}

function renderActiveProfile() {
  const panel = $("#activeProfile");
  if (!reviewState.activeProfileId) {
    panel.hidden = true;
    return;
  }
  const profile = reviewState.profiles.find((item) => item.profile_id === reviewState.activeProfileId);
  panel.hidden = false;
  panel.replaceChildren();
  const title = document.createElement("h3");
  setText(title, profile ? profile.display_name : reviewState.activeProfileId);
  const meta = document.createElement("p");
  setText(meta, profile ? `${profile.profile_id} · ${(profile.roles || []).join(", ")}` : "Profile not registered on server");
  panel.append(title, meta);
}

function renderQueueList() {
  const list = $("#queueList");
  list.replaceChildren();
  for (const item of reviewState.items) {
    const button = document.createElement("button");
    button.className = `case-item${reviewState.activeItemId === item.item_id ? " active" : ""}`;
    button.type = "button";
    button.setAttribute("role", "option");
    button.setAttribute("aria-selected", reviewState.activeItemId === item.item_id ? "true" : "false");
    const strong = document.createElement("strong");
    setText(strong, item.item_id);
    const meta = document.createElement("span");
    setText(meta, `${item.source_id} · ${item.queue_status} · ${item.opinion_count ?? 0} opinion(s)`);
    button.append(strong, meta);
    button.addEventListener("click", () => openItem(item.item_id));
    list.append(button);
  }
}

function renderCaptureDiff(captureDiff) {
  const holder = $("#captureDiff");
  holder.replaceChildren();
  if (!captureDiff?.available) {
    const p = document.createElement("p");
    p.className = "muted";
    setText(p, captureDiff?.reason || "Diff unavailable");
    holder.append(p);
    return;
  }
  if (captureDiff.mode === "single_snapshot") {
    const pre = document.createElement("pre");
    pre.className = "capture-preview mono";
    pre.setAttribute("data-sandbox", "text-only");
    setText(pre, captureDiff.preview_text || "");
    holder.append(pre);
    return;
  }
  const pre = document.createElement("pre");
  pre.className = "capture-preview mono";
  pre.setAttribute("data-sandbox", "text-only");
  for (const line of captureDiff.lines || []) {
    const span = document.createElement("span");
    span.className = `diff-${line.kind || "context"}`;
    setText(span, line.text || "");
    pre.append(span, document.createTextNode("\n"));
  }
  holder.append(pre);
}

function renderAdjudicationFields(fields) {
  const holder = $("#adjudicationFields");
  holder.replaceChildren();
  for (const field of fields || []) {
    const label = document.createElement("label");
    const legend = document.createElement("span");
    setText(legend, field.label + (field.required ? " *" : ""));
    label.append(legend);
    let control;
    if (field.control === "select") {
      control = document.createElement("select");
      control.name = field.name;
      control.required = Boolean(field.required);
      const blank = document.createElement("option");
      blank.value = "";
      setText(blank, "Select…");
      control.append(blank);
      for (const option of field.options || []) {
        const node = document.createElement("option");
        node.value = option;
        setText(node, option);
        control.append(node);
      }
    } else if (field.control === "textarea") {
      control = document.createElement("textarea");
      control.name = field.name;
      control.required = Boolean(field.required);
      control.rows = 4;
    } else if (field.control === "profile") {
      control = document.createElement("input");
      control.type = "text";
      control.name = field.name;
      control.required = Boolean(field.required);
      control.value = reviewState.activeProfileId || "";
      control.readOnly = Boolean(reviewState.activeProfileId);
    } else {
      control = document.createElement("input");
      control.type = "text";
      control.name = field.name;
      control.required = Boolean(field.required);
    }
    label.append(control);
    if (field.help) {
      const help = document.createElement("small");
      help.className = "muted";
      setText(help, field.help);
      label.append(help);
    }
    holder.append(label);
  }
}

function renderOpinions(opinions) {
  const holder = $("#opinionList");
  holder.replaceChildren();
  if (!opinions?.length) {
    const p = document.createElement("p");
    p.className = "muted";
    setText(p, "No opinions recorded.");
    holder.append(p);
    return;
  }
  const tableWrap = document.createElement("div");
  tableWrap.className = "table-wrap";
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const title of ["Profile", "Role", "Position", "Rationale"]) {
    const th = document.createElement("th");
    setText(th, title);
    headRow.append(th);
  }
  thead.append(headRow);
  const tbody = document.createElement("tbody");
  for (const opinion of opinions) {
    const tr = document.createElement("tr");
    for (const value of [opinion.reviewer_profile_id, opinion.role, opinion.position, opinion.rationale]) {
      const td = document.createElement("td");
      if (value === opinion.position) td.append(badge(value));
      else setText(td, value);
      tr.append(td);
    }
    tbody.append(tr);
  }
  table.append(thead, tbody);
  tableWrap.append(table);
  holder.append(tableWrap);
}

function updateLeaseControls(detail) {
  const lease = detail?.item?.active_lease;
  reviewState.activeLeaseId = lease?.lease_id || null;
  $("#releaseLease").hidden = !lease || lease.reviewer_profile_id !== reviewState.activeProfileId;
}

async function loadHealth() {
  reviewState.health = await api("/api/review/health");
  renderOpsHealth(reviewState.health);
  const statusBits = [];
  if (reviewState.health.monitoring_initialized) statusBits.push("monitoring ready");
  if (reviewState.health.queue?.initialized) statusBits.push(`${reviewState.items.length} queue item(s)`);
  else statusBits.push("review queue not initialized");
  setText($("#reviewState"), statusBits.join(" · "));
}

async function loadProfiles() {
  const payload = await api("/api/review/profiles");
  reviewState.profiles = payload.profiles || [];
  renderProfileRoleOptions(payload.fields || []);
  if (reviewState.activeProfileId) $("#profileId").value = reviewState.activeProfileId;
  renderActiveProfile();
}

async function loadQueue() {
  const payload = await api("/api/review/queue");
  reviewState.items = payload.items || [];
  renderQueueList();
}

async function openItem(itemId) {
  reviewState.activeItemId = itemId;
  reviewState.detail = await api(`/api/review/queue/${encodeURIComponent(itemId)}`);
  $("#reviewEmpty").hidden = true;
  $("#reviewView").hidden = false;
  setText($("#itemTitle"), itemId);
  setText($("#itemMeta"), `${reviewState.detail.item.source_id} · ${reviewState.detail.item.queue_status}`);
  setText($("#candidateSummary"), reviewState.detail.candidate.summary || "");
  const meta = $("#candidateMeta");
  meta.replaceChildren();
  const rows = [
    ["Candidate ID", reviewState.detail.candidate.candidate_id],
    ["Status", reviewState.detail.candidate.status],
    ["Proposed materiality", reviewState.detail.candidate.proposed_materiality],
    ["Monitoring hash", reviewState.detail.item.monitoring_record_sha256],
  ];
  for (const [key, value] of rows) {
    const dt = document.createElement("dt"); setText(dt, key);
    const dd = document.createElement("dd"); dd.className = key.includes("hash") ? "mono" : ""; setText(dd, value);
    meta.append(dt, dd);
  }
  renderCaptureDiff(reviewState.detail.capture_diff);
  renderAdjudicationFields(reviewState.detail.adjudication_fields);
  renderOpinions(reviewState.detail.opinions);
  updateLeaseControls(reviewState.detail);
  renderQueueList();
}

$("#profileForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const profileId = $("#profileId").value.trim();
    const displayName = $("#profileDisplayName").value.trim();
    const roles = $$("#profileRoles input:checked").map((node) => node.value);
    await api("/api/review/profiles", {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId, display_name: displayName, roles }),
    });
    reviewState.activeProfileId = profileId;
    localStorage.setItem("neuroai.review.profileId", profileId);
    showToast("Local reviewer profile saved.");
    await loadProfiles();
    renderAdjudicationFields(reviewState.detail?.adjudication_fields || []);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#initReviewQueue").addEventListener("click", async () => {
  try {
    await api("/api/review/init", { method: "POST", body: JSON.stringify({}) });
    showToast("Review queue initialized.");
    await Promise.all([loadHealth(), loadQueue()]);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#claimLease").addEventListener("click", async () => {
  if (!reviewState.activeItemId || !reviewState.activeProfileId) {
    showToast("Select an item and register a local profile first.", true);
    return;
  }
  try {
    await api(`/api/review/queue/${encodeURIComponent(reviewState.activeItemId)}/lease`, {
      method: "POST",
      body: JSON.stringify({ reviewer_profile_id: reviewState.activeProfileId }),
    });
    showToast("Lease claimed.");
    await openItem(reviewState.activeItemId);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#releaseLease").addEventListener("click", async () => {
  if (!reviewState.activeLeaseId || !reviewState.activeProfileId) return;
  try {
    await api(`/api/review/leases/${encodeURIComponent(reviewState.activeLeaseId)}/release`, {
      method: "POST",
      body: JSON.stringify({ reviewer_profile_id: reviewState.activeProfileId }),
    });
    showToast("Lease released.");
    await openItem(reviewState.activeItemId);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#opinionForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!reviewState.activeItemId || !reviewState.activeProfileId) {
    showToast("Select an item and register a local profile first.", true);
    return;
  }
  try {
    await api(`/api/review/queue/${encodeURIComponent(reviewState.activeItemId)}/opinion`, {
      method: "POST",
      body: JSON.stringify({
        reviewer_profile_id: reviewState.activeProfileId,
        position: $("#opinionPosition").value,
        rationale: $("#opinionRationale").value,
      }),
    });
    showToast("Opinion submitted.");
    event.target.reset();
    await openItem(reviewState.activeItemId);
  } catch (error) {
    showToast(error.message, true);
  }
});

$("#adjudicationForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!reviewState.activeItemId) {
    showToast("Select a queue item first.", true);
    return;
  }
  const body = Object.fromEntries(new FormData(event.target).entries());
  if (!body.decided_by && reviewState.activeProfileId) body.decided_by = reviewState.activeProfileId;
  try {
    await api(`/api/review/queue/${encodeURIComponent(reviewState.activeItemId)}/adjudicate`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    showToast("Adjudication recorded.");
    event.target.reset();
    await Promise.all([loadHealth(), loadQueue()]);
    await openItem(reviewState.activeItemId);
  } catch (error) {
    showToast(error.message, true);
  }
});

(async function init() {
  try {
    await Promise.all([loadHealth(), loadProfiles()]);
    try {
      await loadQueue();
    } catch (error) {
      setText($("#reviewState"), `Review queue unavailable: ${error.message}`);
    }
  } catch (error) {
    setText($("#reviewState"), `Failed to load: ${error.message}`);
    showToast(error.message, true);
  }
})();
