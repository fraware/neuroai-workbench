"use strict";

const state = { cases: [], activeCase: null, assessment: null, summary: null, validation: null, kernel: [] };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

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
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast${error ? " error" : ""}`;
  toast.hidden = false;
  window.setTimeout(() => { toast.hidden = true; }, 5000);
}

function escapeText(value) { return String(value ?? ""); }
function statusClass(value) {
  const lowered = String(value || "").toLowerCase();
  if (lowered.includes("pass") || lowered === "valid") return "pass";
  if (lowered.includes("partial") || lowered.includes("warning")) return "partial";
  if (lowered.includes("fail") || lowered.includes("invalid") || lowered.includes("block")) return "fail";
  return "na";
}
function badge(value) {
  const span = document.createElement("span");
  span.className = `status ${statusClass(value)}`;
  span.textContent = value;
  return span;
}

async function loadCases(selectId = null) {
  const payload = await api("/api/cases");
  state.cases = payload.cases;
  const list = $("#caseList");
  list.replaceChildren();
  for (const item of state.cases) {
    const button = document.createElement("button");
    button.className = `case-item${state.activeCase === item.case_id ? " active" : ""}`;
    const strong = document.createElement("strong"); strong.textContent = item.title || item.case_id;
    const meta = document.createElement("span");
    meta.textContent = `${item.case_id} · ${item.valid ? "valid" : "needs work"} · ${item.p0_blockers ?? "?"} P0 blockers`;
    button.append(strong, meta);
    button.addEventListener("click", () => openCase(item.case_id));
    list.append(button);
  }
  $("#workspaceState").textContent = `${state.cases.length} case${state.cases.length === 1 ? "" : "s"} in local workspace`;
  if (selectId) await openCase(selectId);
}

async function openCase(caseId) {
  state.activeCase = caseId;
  const [assessment, summary, validation] = await Promise.all([
    api(`/api/cases/${encodeURIComponent(caseId)}/assessment`),
    api(`/api/cases/${encodeURIComponent(caseId)}/summary`),
    api(`/api/cases/${encodeURIComponent(caseId)}/validate`),
  ]);
  state.assessment = assessment; state.summary = summary; state.validation = validation;
  $("#emptyState").hidden = true; $("#caseView").hidden = false;
  $("#caseTitle").textContent = summary.title || caseId;
  $("#caseMeta").textContent = `${summary.assessment_id} · ${summary.system_name} · ${summary.profile_id} / ${summary.target_level}`;
  $("#jsonEditor").value = JSON.stringify(assessment, null, 2);
  renderSummary(); renderRequirements(); renderDecisions();
  await Promise.all([loadEvidence(), loadEvents()]);
  await loadCases();
}

function renderSummary() {
  const counts = state.summary.counts;
  const cards = [
    [counts.claims, "Claims"], [counts.evidence_objects, "Evidence"], [counts.endpoints, "Endpoints"],
    [counts.pass, "PASS"], [counts.partial, "PARTIAL"], [counts.fail, "FAIL"],
    [counts.not_assessed, "Not assessed"], [counts.p0_blockers, "P0 blockers"],
  ];
  const holder = $("#summaryCards"); holder.replaceChildren();
  for (const [value, label] of cards) {
    const card = document.createElement("div"); card.className = "card";
    const v = document.createElement("div"); v.className = "value"; v.textContent = value;
    const l = document.createElement("div"); l.className = "label"; l.textContent = label;
    card.append(v, l); holder.append(card);
  }
  const validation = $("#validationState"); validation.replaceChildren();
  validation.append(badge(state.validation.valid ? "VALID" : "INVALID"));
  const p = document.createElement("p");
  p.textContent = `${state.validation.schema_issues.length} schema errors, ${state.validation.semantic_issues.length} semantic errors, ${state.validation.warnings.length} warnings.`;
  validation.append(p, issueList([...state.validation.schema_issues, ...state.validation.semantic_issues, ...state.validation.warnings].slice(0, 12)));
  const blockers = $("#p0Blockers"); blockers.replaceChildren();
  if (!state.summary.p0_blocker_ids.length) blockers.textContent = "No mechanical P0 blocker is recorded.";
  else blockers.append(issueList(state.summary.p0_blocker_ids.map(id => ({ message: id }))));
  const summaryDecisions = $("#summaryDecisions"); summaryDecisions.replaceChildren();
  for (const decision of state.assessment.decision_register || []) summaryDecisions.append(decisionCard(decision));
}

function issueList(issues) {
  const ul = document.createElement("ul"); ul.className = "issue-list";
  if (!issues.length) { const li = document.createElement("li"); li.textContent = "None recorded."; ul.append(li); }
  for (const issue of issues) {
    const li = document.createElement("li");
    li.textContent = [issue.code, issue.path, issue.message].filter(Boolean).join(" · ");
    ul.append(li);
  }
  return ul;
}

function renderRequirements() {
  const titleMap = Object.fromEntries(state.kernel.map(row => [row.Requirement_ID, row.Title || row.Requirement_Title || ""]));
  const tbody = $("#requirementsTable tbody"); tbody.replaceChildren();
  const search = $("#requirementSearch").value.trim().toLowerCase();
  const status = $("#statusFilter").value;
  const priority = $("#priorityFilter").value;
  for (const row of state.assessment.requirement_findings || []) {
    const text = `${row.requirement_id} ${titleMap[row.requirement_id] || ""} ${row.finding || ""}`.toLowerCase();
    if (search && !text.includes(search)) continue;
    if (status && row.finding_status !== status) continue;
    if (priority && row.priority !== priority) continue;
    const tr = document.createElement("tr");
    const values = [row.requirement_id, row.module_id, row.priority, row.applicability, row.finding_status, row.finding, (row.evidence_ids || []).join(", ")];
    values.forEach((value, index) => {
      const td = document.createElement("td");
      if (index === 4) td.append(badge(value)); else td.textContent = escapeText(value);
      tr.append(td);
    });
    tbody.append(tr);
  }
}

function decisionCard(decision) {
  const article = document.createElement("article"); article.className = "panel decision";
  const h = document.createElement("h3"); h.textContent = `${decision.decision_object_type} — ${decision.decision_state}`;
  const dl = document.createElement("dl");
  const rows = [
    ["Decision ID", decision.decision_id], ["Authority", decision.authority], ["Authority basis", decision.authority_basis],
    ["Strongest supported claim", decision.strongest_supported_claim],
    ["Prohibited inferences", (decision.prohibited_inferences || []).join("\n")],
    ["Conditions", (decision.conditions || []).join("\n")], ["Expiry", decision.expiry],
    ["Reopening triggers", (decision.reopening_triggers || []).join("\n")],
  ];
  for (const [key, value] of rows) { const dt=document.createElement("dt");dt.textContent=key;const dd=document.createElement("dd");dd.textContent=escapeText(value);dl.append(dt,dd); }
  article.append(h, dl); return article;
}
function renderDecisions() {
  const holder = $("#decisionList"); holder.replaceChildren();
  for (const decision of state.assessment.decision_register || []) holder.append(decisionCard(decision));
}

async function loadEvidence() {
  if (!state.activeCase) return;
  const payload = await api(`/api/cases/${encodeURIComponent(state.activeCase)}/evidence`);
  const verification = $("#evidenceVerification"); verification.replaceChildren();
  verification.append(badge(payload.verification.valid ? "DIGESTS VALID" : "DIGEST FAILURE"));
  const p = document.createElement("p"); p.textContent = `${payload.verification.object_count} local evidence object(s). Byte identity is distinct from substantive appraisal.`; verification.append(p);
  const tbody = $("#evidenceTable tbody"); tbody.replaceChildren();
  for (const item of payload.objects) {
    const tr = document.createElement("tr");
    [item.evidence_id, item.title, item.original_filename, item.size_bytes, item.sha256, item.added_at].forEach((value, i) => {
      const td=document.createElement("td");td.textContent=escapeText(value);if(i===4)td.className="mono";tr.append(td);
    });
    tbody.append(tr);
  }
}

async function loadEvents() {
  if (!state.activeCase) return;
  const payload = await api(`/api/cases/${encodeURIComponent(state.activeCase)}/events`);
  const verification = $("#eventVerification"); verification.replaceChildren();
  verification.append(badge(payload.verification.valid ? "HASH CHAIN VALID" : "HASH CHAIN INVALID"));
  const p=document.createElement("p");p.textContent=`${payload.verification.event_count} event(s); head ${payload.verification.head_hash}. Log integrity does not establish statement truth.`;verification.append(p);
  const tbody=$("#eventsTable tbody");tbody.replaceChildren();
  for(const item of payload.events){const tr=document.createElement("tr");[item.seq,item.timestamp,item.actor,item.action,item.event_hash].forEach((value,i)=>{const td=document.createElement("td");td.textContent=escapeText(value);if(i===4)td.className="mono";tr.append(td)});tbody.append(tr)}
}

async function refreshCurrent() { if (state.activeCase) await openCase(state.activeCase); }

$("#createCase").addEventListener("click", () => $("#newCaseDialog").showModal());
$("#newCaseForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const caseId=$("#newCaseId").value.trim(); const title=$("#newCaseTitle").value.trim();
    await api("/api/cases", {method:"POST", body:JSON.stringify({case_id:caseId,title})});
    $("#newCaseDialog").close(); showToast("Case created."); await loadCases(caseId);
  } catch (error) { showToast(error.message, true); }
});
$("#importCase").addEventListener("change", async (event) => {
  const file=event.target.files[0]; if(!file)return;
  try { const assessment=JSON.parse(await file.text()); await api("/api/import",{method:"POST",body:JSON.stringify({assessment})}); showToast("Assessment imported."); await loadCases(assessment.assessment_metadata.assessment_id); }
  catch(error){showToast(error.message,true)} finally {event.target.value=""}
});
[$("#requirementSearch"),$("#statusFilter"),$("#priorityFilter")].forEach(control => control.addEventListener("input", renderRequirements));
$("#validateCase").addEventListener("click", async()=>{try{state.validation=await api(`/api/cases/${encodeURIComponent(state.activeCase)}/validate`);renderSummary();showToast(state.validation.valid?"Validation passed.":"Validation found controlled issues.",!state.validation.valid)}catch(error){showToast(error.message,true)}});
$("#snapshotCase").addEventListener("click", async()=>{try{await api(`/api/cases/${encodeURIComponent(state.activeCase)}/snapshot`,{method:"POST",body:JSON.stringify({label:"manual"})});showToast("Snapshot created.");await loadEvents()}catch(error){showToast(error.message,true)}});
$("#bundleCase").addEventListener("click",()=>{if(state.activeCase)window.location=`/api/cases/${encodeURIComponent(state.activeCase)}/bundle`});
$("#formatJson").addEventListener("click",()=>{try{$("#jsonEditor").value=JSON.stringify(JSON.parse($("#jsonEditor").value),null,2)}catch(error){showToast(error.message,true)}});
$("#saveJson").addEventListener("click",async()=>{try{const assessment=JSON.parse($("#jsonEditor").value);const report=await api(`/api/cases/${encodeURIComponent(state.activeCase)}/assessment`,{method:"PUT",body:JSON.stringify({assessment,require_valid:$("#requireValidSave").checked})});showToast(report.valid?"Assessment saved and valid.":"Assessment saved with controlled issues.",!report.valid);await refreshCurrent()}catch(error){showToast(error.message,true)}});
$("#evidenceForm").addEventListener("submit",async(event)=>{event.preventDefault();const file=$("#evidenceFile").files[0];if(!file)return;try{const bytes=new Uint8Array(await file.arrayBuffer());let binary="";for(let i=0;i<bytes.length;i+=0x8000)binary+=String.fromCharCode(...bytes.subarray(i,i+0x8000));const content_base64=btoa(binary);await api(`/api/cases/${encodeURIComponent(state.activeCase)}/evidence`,{method:"POST",body:JSON.stringify({filename:file.name,content_base64,title:$("#evidenceTitle").value,evidence_type:$("#evidenceType").value,source:$("#evidenceSource").value,link_to_assessment:true})});showToast("Evidence bytes registered and linked.");event.target.reset();await refreshCurrent()}catch(error){showToast(error.message,true)}});

(async function init(){
  try { state.kernel=await api("/api/resources/kernel"); await loadCases(); }
  catch(error){$("#workspaceState").textContent=`Failed to load: ${error.message}`;showToast(error.message,true)}
})();
