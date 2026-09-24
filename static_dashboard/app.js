"use strict";

import { clearSpecialPage, renderSpecialPage } from "./page-visuals.js?v=20260924-3";
import { renderInsightsPage } from "./insights-visuals.js?v=20260924-3";

const state = { catalog: null, page: "overview", course: "", offering: "", assignments: new Set(), interval: "day", mode: "scored", supportTopic: "all", insightsTab: "exploration", insightArea: "engagement_grade", explorationTarget: "AT1", modelTarget: "all" };
const pageNames = {
  overview: "Overview", engagement: "Engagement", assignments: "Assignments",
  outcomes: "Feedback", insights: "Insights", "data-rules": "Data & Rules"
};
if (location.hash.slice(1) in pageNames) state.page = location.hash.slice(1);
const knownLabels = {
  students: "Students", offerings: "Offerings", courses: "Courses", records: "Records",
  macro_f1: "Macro F1", balanced_accuracy: "Balanced Accuracy",
  engagement_students: "Students with Canvas activity", assignment_students: "Total number of students",
  valid_award_holders: "Students with an active Badge", cohort_memberships: "Students represented",
  mean_score_pct: "Mean score (%)", submission_rate_pct: "Submission rate (%)",
};
const cohortLabels = {
  source_specific: "Student groups from each available data source",
  all_engagement: "Students with Canvas activity in the selected teaching period",
  all_assignment: "Students with assignment records in the selected teaching period",
  completed_qualtrics_responses: "Completed anonymous Qualtrics responses in the selected teaching period",
  course_separated_student_offering_records: "Linked student records pooled across teaching periods for this course",
  metadata_only: "Source and rule metadata for the selected scope"
};
const colours = ["#355b88", "#d97706", "#16856b", "#8b5cf6", "#dc4c64", "#64748b"];
let pageRequest = 0;
const staticSnapshot = window.__MPE_STATIC_SNAPSHOT__ || null;
const staticMode = Boolean(staticSnapshot);

const el = id => document.getElementById(id);
const escapeHtml = value => String(value ?? "").replace(/[&<>'"]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[character]);
const label = key => knownLabels[key] || String(key).replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
const shortLabel = value => String(value).length > 30 ? String(value).slice(0, 27) + "…" : String(value);
const offeringLabel = value => {
  const match = String(value || "").trim().match(/^(?:[A-Z0-9]+[ _-]+)?(\d{4})[ _-]+([A-Z]{3})[ _-]+PAR[ _-]+(\d+)$/i);
  return match ? `${match[1]} ${match[2].toUpperCase()} PAR ${match[3]}` : String(value || "Unknown");
};

async function api(path, options = {}) {
  if (staticMode) {
    const method = (options.method || "GET").toUpperCase();
    if (method !== "GET") throw new Error("This action is available in the internal live application only");
    const url = new URL(path, "https://snapshot.local");
    const query = [...url.searchParams.entries()].sort(([aKey, aValue], [bKey, bValue]) =>
      aKey.localeCompare(bKey) || aValue.localeCompare(bValue));
    const key = url.pathname + (query.length ? `?${new URLSearchParams(query)}` : "");
    const payload = staticSnapshot.responses?.[key];
    if (payload === undefined) throw new Error("This filter combination is not included in the static snapshot");
    return structuredClone(payload);
  }
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  if (!response.ok) throw new Error(`Request failed (HTTP ${response.status})`);
  return response.json();
}

function metricValue(metric) {
  if (!metric || metric.value === null || metric.value === undefined) return '<span class="unavailable">Not available</span>';
  if (typeof metric.value === "number") return metric.value.toLocaleString("en-AU", { maximumFractionDigits: 2 });
  return escapeHtml(metric.value);
}

function renderMetrics(metrics) {
  el("metrics").innerHTML = Object.entries(metrics || {}).map(([key, value]) =>
    `<article class="card"><div class="label">${label(key)}</div><div class="value">${metricValue(value)}</div></article>`
  ).join("");
}

function numericKeys(rows) {
  return [...new Set(rows.flatMap(row => Object.entries(row.metrics || {})
    .filter(([, metric]) => typeof metric?.value === "number").map(([key]) => key)))];
}

function preferredMetric(title, keys) {
  const priorities = title.includes("association") ? ["spearman_rho", "within_offering_rank_r"]
    : title.includes("activity") ? ["views", "participations", "students"]
    : title.includes("score") || title.includes("grade") ? ["students", "mean_score_pct", "records"]
    : title.includes("badge") || title.includes("award") ? ["memberships", "holders", "award_records", "records"]
    : ["students", "records", "memberships", "views", "participations"];
  return priorities.find(key => keys.includes(key)) || keys.find(key => !key.endsWith("_n")) || keys[0];
}

function barChart(title, rows, valueKey) {
  const items = rows.filter(row => typeof row.metrics?.[valueKey]?.value === "number").slice(0, 16);
  if (items.length < 2) return "";
  const values = items.map(row => Number(row.metrics[valueKey].value));
  const min = Math.min(0, ...values), max = Math.max(0, ...values);
  const width = 900, rowHeight = 30, top = 24, bottom = 24, labelWidth = 220, right = 65;
  const height = top + bottom + items.length * rowHeight;
  const span = max - min || 1;
  const x = value => labelWidth + (value - min) * (width - labelWidth - right) / span;
  const zero = x(0);
  const rowsSvg = items.map((row, index) => {
    const value = Number(row.metrics[valueKey].value), end = x(value), start = Math.min(zero, end), barWidth = Math.max(Math.abs(end - zero), 1);
    return `<text x="${labelWidth-10}" y="${top+index*rowHeight+18}" text-anchor="end">${escapeHtml(shortLabel(offeringLabel(row.label)))}</text><rect x="${start}" y="${top+index*rowHeight+5}" width="${barWidth}" height="17" rx="2" fill="${value < 0 ? colours[4] : colours[0]}"/><text x="${value < 0 ? start-5 : end+5}" y="${top+index*rowHeight+18}" text-anchor="${value < 0 ? "end" : "start"}">${value.toLocaleString("en-AU", {maximumFractionDigits:2})}</text>`;
  }).join("");
  return `<div class="chart"><div class="chart-title">${label(valueKey)}</div><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label(valueKey))} bar chart"><line x1="${zero}" y1="${top}" x2="${zero}" y2="${height-bottom}" class="axis"/>${rowsSvg}</svg>${rows.length > items.length ? `<p class="chart-note">Showing the first ${items.length} of ${rows.length} categories. Use the data table for all values.</p>` : ""}</div>`;
}

function renderChart(title, rows) {
  const keys = numericKeys(rows);
  if (!keys.length) return "";
  const key = preferredMetric(title, keys);
  return barChart(title, rows, key);
}

function renderRows(title, rows, open = false) {
  if (!rows?.length) return "";
  if (["survey_feedback_comments", "support_issue_summaries", "analysis_questions"].includes(title)) {
    return `<section class="visual"><h3>${label(title)}</h3><div class="text-grid">${rows.map(row =>
      `<article class="text-card"><div class="text-meta">${escapeHtml(row.dimensions?.question_group || row.dimensions?.topic || row.dimensions?.analysis_area || "")}</div><p>${escapeHtml(row.label)}</p>${row.dimensions?.result ? `<small>${escapeHtml(row.dimensions.result)}</small>` : ""}${row.metrics?.responses ? `<strong>${metricValue(row.metrics.responses)} response${row.metrics.responses.value === 1 ? "" : "s"}</strong>` : ""}</article>`
    ).join("")}</div></section>`;
  }
  const dimensions = [...new Set(rows.flatMap(row => Object.keys(row.dimensions || {})))];
  const metrics = [...new Set(rows.flatMap(row => Object.keys(row.metrics || {})))];
  const headings = ["Item", ...dimensions.map(label), ...metrics.map(label)];
  const body = rows.map(row => `<tr><td>${escapeHtml(offeringLabel(row.label))}</td>${dimensions.map(key =>
    `<td>${escapeHtml(key === "offering" ? offeringLabel(row.dimensions?.[key]) : row.dimensions?.[key] ?? "—")}</td>`).join("")}${metrics.map(key =>
    `<td>${metricValue(row.metrics?.[key])}</td>`).join("")}</tr>`).join("");
  return `<section class="visual"><h3>${label(title)}</h3>${renderChart(title, rows)}<details ${open ? "open" : ""}><summary>View data (${rows.length} rows)</summary><div class="table-wrap"><table><thead><tr>${headings.map(heading =>
    `<th>${heading}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div></details></section>`;
}


function renderTables(data) {
  return Object.entries(data.tables || {}).map(([key, rows], index) => renderRows(key, rows, index === 0)).join("");
}

function currentParams(extra = {}) {
  const params = new URLSearchParams({ course: state.course, ...extra });
  if (state.offering && state.page !== "insights") params.set("offering", state.offering);
  return params;
}

function filterMarkup() {
  if (state.page === "engagement") return `<label>Time interval<select id="interval"><option value="day">Day</option><option value="week">Week</option><option value="month">Month</option></select></label>`;
  if (state.page === "assignments") return `<label>Assignment type<select id="mode"><option value="combined">All activities</option><option value="scored">Scored</option><option value="self_assessment">Self-assessment</option></select></label><fieldset class="assignment-picker"><legend>Assignments</legend><div id="assignmentChoices">Loading…</div></fieldset>`;
  return "";
}

function bindPageFilters() {
  if (el("interval")) { el("interval").value = state.interval; el("interval").onchange = event => { state.interval = event.target.value; loadPage(); }; }
  if (el("mode")) { el("mode").value = state.mode; el("mode").onchange = event => { state.mode = event.target.value; state.assignments.clear(); loadPage(); }; }
}

async function retrain(event) {
  const button = event?.currentTarget;
  if (!button || state.modelTarget === "all") return;
  const originalText = button.textContent;
  button.disabled = true; button.textContent = "Training…";
  try {
    const result = await api("/v1/models/train", { method: "POST", body: JSON.stringify({ course: state.course, target: state.modelTarget }) });
    showMessage(result.already_current ? "Data and configuration are unchanged. The current model remains active." : `Training finished with status: ${result.status}.`);
    await loadPage();
  } catch (error) { showMessage(error.message); }
  finally { if (button.isConnected) { button.disabled = false; button.textContent = originalText; } }
}

async function loadAssignmentOptions() {
  const picker = el("assignmentChoices");
  if (!picker) return;
  const options = await api(`/v1/assignment-options?${currentParams({ mode: state.mode })}`);
  const valid = new Set(options.map(item => item.ref));
  state.assignments = new Set([...state.assignments].filter(ref => valid.has(ref)));
  picker.innerHTML = options.length ? options.map(item => `<label><input type="checkbox" value="${escapeHtml(item.ref)}" ${state.assignments.has(item.ref) ? "checked" : ""}><span>${escapeHtml(item.assessment_key || item.name)}</span></label>`).join("") : `<span class="unavailable">No assignments available</span>`;
  picker.querySelectorAll("input").forEach(input => input.onchange = () => {
    if (staticMode) state.assignments.clear();
    input.checked ? state.assignments.add(input.value) : state.assignments.delete(input.value);
    loadPage();
  });
}

function showMessage(message = "") {
  el("message").hidden = !message;
  el("message").textContent = message;
}

async function loadPage() {
  if (!state.course) return;
  const requestId = ++pageRequest;
  document.querySelector("main").classList.add("loading");
  showMessage();
  el("pageTitle").textContent = pageNames[state.page];
  el("pageFilters").innerHTML = filterMarkup();
  bindPageFilters();
  const extra = {};
  if (state.page === "engagement") extra.interval = state.interval;
  if (state.page === "assignments") {
    extra.mode = state.mode;
    try { await loadAssignmentOptions(); } catch (error) { showMessage(error.message); }
    if (requestId !== pageRequest) return;
    if (state.assignments.size) extra.assignments = [...state.assignments].join(",");
  }
  if (state.page === "insights") extra.target = state.explorationTarget;
  try {
    const data = await api(`/v1/${state.page}?${currentParams(extra)}`);
    if (requestId !== pageRequest) return;
    const models = state.page === "insights" ? await api(`/v1/models?${new URLSearchParams({course: state.course})}`) : null;
    if (requestId !== pageRequest) return;
    el("cohort").textContent = `Population included: ${cohortLabels[data.cohort] || label(data.cohort)}`;
    clearSpecialPage(el);
    el("modelPanel").innerHTML = "";
    if (state.page === "insights") {
      renderInsightsPage(data, models, {state, metrics:el("metrics"), coverage:el("coverage"), tables:el("tables"), notes:el("notes"), reload:loadPage, retrain, staticMode});
    } else if (!renderSpecialPage(data, { state, el })) {
      renderMetrics(data.metrics);
      el("coverage").innerHTML = "";
      el("tables").innerHTML = renderTables(data);
      el("notes").innerHTML = data.notes?.length ? `<div class="panel notes"><h3>Definitions and limitations</h3><ul>${data.notes.map(note => `<li>${escapeHtml(note)}</li>`).join("")}</ul></div>` : "";
    }
    if (state.page === "data-rules") await renderRules();
  } catch (error) {
    if (requestId !== pageRequest) return;
    showMessage(error.message);
    ["metrics", "coverage", "modelPanel", "tables", "notes"].forEach(id => el(id).innerHTML = "");
  } finally { if (requestId === pageRequest) document.querySelector("main").classList.remove("loading"); }
}

async function renderRules() {
  const rules = await api(`/v1/rules?${currentParams()}`);
  const rows = rules.rules.map(rule => ({
    label: rule.version,
    dimensions: { course: rule.course, offering: rule.offering ? offeringLabel(rule.offering) : "Course default", status: rule.status, enabled: String(rule.enabled), pass_threshold: String(rule.pass_threshold) },
    metrics: {}
  }));
  el("tables").insertAdjacentHTML("afterbegin", renderRows("Assessment rules", rows, true));
}

function populateOfferings() {
  const options = state.catalog.offerings.filter(item => item.course === state.course)
    .sort((a, b) => String(b.starts_on || "").localeCompare(String(a.starts_on || "")) || a.code.localeCompare(b.code));
  const assignmentPage = state.page === "assignments";
  el("offering").innerHTML = `${assignmentPage ? "" : '<option value="">All teaching periods</option>'}${options.map(item =>
    `<option value="${escapeHtml(item.code)}">${escapeHtml(offeringLabel(item.code))} · ${escapeHtml(item.starts_on || "Date unknown")}</option>`).join("")}`;
  if (!options.some(item => item.code === state.offering)) state.offering = assignmentPage ? options[0]?.code || "" : "";
  if (assignmentPage && !state.offering) state.offering = options[0]?.code || "";
  el("offering").value = state.offering;
}

function syncOfferingControl() {
  const pooled = state.page === "insights";
  el("offering").disabled = pooled;
  el("offering").value = pooled ? "" : state.offering;
}

async function start() {
  try {
    const health = await api("/v1/health");
    if (health.database !== "ok") throw new Error("The database is unavailable");
    state.catalog = await api("/v1/catalog");
    el("course").innerHTML = state.catalog.courses.map(item => `<option value="${escapeHtml(item.code)}">${escapeHtml(item.name)}</option>`).join("");
    state.course = state.catalog.courses[0]?.code || "";
    el("course").value = state.course;
    populateOfferings();
    document.querySelector("nav button.active")?.classList.remove("active");
    document.querySelector(`nav button[data-page="${state.page}"]`)?.classList.add("active");
    syncOfferingControl();
    el("course").onchange = event => { state.course = event.target.value; state.offering = ""; state.assignments.clear(); populateOfferings(); syncOfferingControl(); loadPage(); };
    el("offering").onchange = event => { state.offering = event.target.value; state.assignments.clear(); loadPage(); };
    document.querySelectorAll("nav button").forEach(button => button.onclick = () => {
      document.querySelector("nav button.active")?.classList.remove("active");
      button.classList.add("active"); state.page = button.dataset.page; location.hash = state.page;
      if (state.page === "outcomes") state.offering = "";
      populateOfferings(); syncOfferingControl(); loadPage();
    });
    el("connection").textContent = staticMode
      ? `Static snapshot · ${staticSnapshot.meta?.generated_at?.slice(0, 10) || "date unavailable"}`
      : "Local data service connected";
    el("connection").className = "status ok";
    await loadPage();
  } catch (error) {
    el("connection").textContent = "Connection failed";
    el("connection").className = "status error";
    showMessage(`${error.message}. Confirm that both local services are running.`);
  }
}

start();
