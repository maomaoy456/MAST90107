"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5"];
const TARGET_LABELS = { pass: "Course pass", badge: "Active Badge" };
const GROUP_LABELS = {
  passed: "Passed", not_passed: "Did not pass", valid_badge: "Active Badge recorded",
  no_valid_badge: "No active Badge recorded", macro_f1: "Macro F1",
  balanced_accuracy: "Balanced Accuracy", logistic_regression: "Logistic regression",
  random_forest: "Random forest", completed: "Completed", insufficient: "Insufficient data",
  never_trained: "Not trained", missing_target_class: "Only one outcome class is available",
  class_has_fewer_than_three_students: "An outcome class has fewer than three students",
  fewer_than_twenty_students: "Fewer than twenty students are available",
  no_valid_three_fold_group_split: "Three student-grouped validation folds cannot be formed"
};

const SUMMARY = [
  "This dashboard brings five data sources together for two Melbourne MicroCerts, Understanding Treaty and PBS: Autism Affirming Practice, across nine teaching periods. The sources are Canvas activity, Canvas assignment records, the Badge export, Salesforce support cases and the Qualtrics end-of-course survey. Every figure is an aggregate: no learner is identified, and every chart carries the table it was drawn from.",
  "Where the data is complete, the outcomes are strong. 254 of 337 Treaty student-teaching-period records have an active Badge, and 258 of 259 records with a complete weighted result met the 70% pass rule. Learners also rate the courses highly: Treaty returned a Net Promoter Score of +46.4% with theme scores between 4.13 and 4.55 out of 5, and PBS returned +72.7% with theme scores between 4.24 and 4.49. The clearest assessment pattern is a drop between the two assessments, with 278 Treaty records showing a graded AT1 but only 259 a graded AT2. The clearest support pattern is that 35 of the 60 verified Salesforce cases concern Canvas access and technology rather than course content.",
  "The main constraint is coverage. The Qualtrics survey is mapped to only 2 of the 9 teaching periods, so the survey findings rest on 39 responses. The PBS Salesforce export has no verified course field, so its cases are excluded from published totals. The sources also disagree on cohort size: Treaty has 337 assignment records and 306 learners with recorded Canvas activity. Predictive models remain exploratory because the pass outcome is highly imbalanced and Badge evidence can be affected by claiming, export and matching gaps."
];
const STANDOUT = [
  "254 of 337 Treaty records have an active Badge",
  "258 of 259 complete weighted results met the 70% pass rule",
  "Net Promoter Score: +46.4% for Treaty and +72.7% for PBS",
  "Graded Treaty records fall from 278 at AT1 to 259 at AT2",
  "35 of 60 verified support cases concern Canvas access or technology",
  "Survey evidence covers 2 of the 9 teaching periods"
];
const esc = item => String(item ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[character]);
const human = item => GROUP_LABELS[item] || TARGET_LABELS[item] || String(item ?? "")
  .replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
const shown = (metric, digits = 0) => metric?.value == null
  ? '<span class="unavailable">Not available</span>'
  : Number(metric.value).toLocaleString("en-AU", { maximumFractionDigits: digits });

function headline(state) {
  const catalog = state.catalog || {courses: [], offerings: []};
  const treaty = catalog.offerings.filter(item => item.course === "0UNDE0001").length;
  const pbs = catalog.offerings.filter(item => item.course === "0AUTI0001").length;
  const items = [
    ["Courses", catalog.courses.length || 2, "Understanding Treaty and PBS"],
    ["Teaching periods", catalog.offerings.length || 9, `${treaty || 7} Treaty, ${pbs || 2} PBS`],
    ["Data sources", 5, "Canvas, assignments, Badge, Salesforce, Qualtrics"],
    ["Recommendations", 8, "5 course actions, 3 data actions"]
  ];
  return `<section class="sr-headline">${items.map(([name, value, detail]) => `<article><span>${esc(name)}</span><strong>${esc(value)}</strong><small>${esc(detail)}</small></article>`).join("")}</section>`;
}

function summaryPage(state) {
  return `${headline(state)}<section class="sr-panel"><div class="sr-head"><h3>What the combined data shows</h3><p>Current findings across the two reviewed MicroCerts and five source systems.</p></div><div class="sr-summary-grid"><div class="sr-prose">${SUMMARY.map(text => `<p>${esc(text)}</p>`).join("")}</div><aside class="sr-standout"><strong>What stands out</strong><ul>${STANDOUT.map(text => `<li>${esc(text)}</li>`).join("")}</ul></aside></div></section>`;
}

function recommendationCards(items) {
  return items.map(row => {
    const number=String(row.key||"").match(/\d+$/)?.[0]||"";
    const groundwork=row.dimensions?.status==="Data groundwork";
    return `<article class="sr-card ${groundwork?"sr-groundwork":""}"><span class="sr-num">${esc(number)}</span><div class="sr-body"><span class="sr-tag">${esc(row.dimensions?.status)}</span><h4>${esc(row.label)}</h4><p><strong>Evidence</strong>${esc(row.dimensions?.evidence)}</p><p class="sr-where"><strong>Where to look</strong>${esc(row.dimensions?.where_to_look)}</p></div></article>`;
  }).join("");
}

function recommendationsPage(data) {
  const rows=data.tables?.recommendations||[];
  const groups=[...new Map(rows.map(row=>[row.dimensions?.group,[row.dimensions?.group,row.dimensions?.group_description]])).values()];
  return `<section class="sr-panel"><div class="sr-head"><h3>Recommendations</h3><p>Eight actions, grouped by where they sit in the learner journey. Each one names the evidence behind it and the page it comes from.</p></div>${groups.map(([group,description])=>`<section class="sr-group"><div class="sr-group-head"><h3>${esc(group)}</h3><p>${esc(description)}</p></div>${recommendationCards(rows.filter(row=>row.dimensions?.group===group))}</section>`).join("")}<p class="sr-closing">Recommendations 1 to 5 are supported by patterns visible in this dashboard. Recommendations 6 to 8 concern the data needed for deeper analysis.</p></section>`;
}

function latestRuns(runs) {
  const latest = new Map();
  for (const run of runs || []) if (!latest.has(run.target) && TARGET_LABELS[run.target]) latest.set(run.target, run);
  return Object.keys(TARGET_LABELS).map(target => latest.get(target) || {
    target, status: "never_trained", class_counts: {}, candidates: {}, included_records: {}, distinct_students: {}, warnings: []
  });
}

function targetCards(runs, selected) {
  return `<div class="target-toolbar"><button data-model-target="all" class="${selected === "all" ? "active" : ""}">All models</button></div><div class="insight-targets">${runs.map(run => `<button data-model-target="${run.target}" class="${selected === run.target ? "active" : ""}"><span>${esc(TARGET_LABELS[run.target])}</span><strong>${shown(run.included_records)} usable records</strong><small class="status-pill ${esc(run.status)}">${esc(human(run.status))}</small></button>`).join("")}</div>`;
}

function modelCard(run, staticMode) {
  const counts = Object.entries(run.class_counts || {});
  const total = counts.reduce((sum, [, metric]) => sum + Number(metric.value || 0), 0);
  const classes = counts.length ? `<div class="model-classes"><div>${counts.map(([name, metric], index) => `<i style="width:${total ? Number(metric.value || 0) / total * 100 : 0}%;background:${COLORS[index]}" title="${esc(human(name))}: ${metric.value ?? "NA"}"></i>`).join("")}</div><div class="legend">${counts.map(([name, metric], index) => `<span><i style="background:${COLORS[index]}"></i>${esc(human(name))} ${metric.value ?? "NA"}</span>`).join("")}</div></div>` : "";
  const candidates = Object.entries(run.candidates || {});
  const comparison = candidates.length ? `<div class="model-comparison">${candidates.map(([name, metrics]) => `<section class="${run.selected_model === name ? "selected" : ""}"><h4>${esc(human(name))}${run.selected_model === name ? " · Selected" : ""}</h4>${["macro_f1", "balanced_accuracy"].map((key, index) => `<div><span>${esc(human(key))}</span><i><b style="width:${Number(metrics[key] || 0) * 100}%;background:${COLORS[index]}"></b></i><strong>${metrics[key] == null ? "NA" : Number(metrics[key]).toFixed(3)}</strong></div>`).join("")}</section>`).join("")}</div><div class="legend"><span><i style="background:${COLORS[0]}"></i>Macro F1</span><span><i style="background:${COLORS[1]}"></i>Balanced Accuracy</span></div>` : `<p class="model-reason">${esc(human(run.reason || "No trained model is available"))}</p>`;
  const warnings = run.warnings?.length ? `<p class="model-warning">${run.warnings.map(human).join(" · ")}</p>` : "";
  const action = staticMode ? '<button class="action" disabled title="Open the internal live application to retrain">Saved snapshot</button>' : `<button class="action" data-retrain="${run.target}">Retrain ${esc(TARGET_LABELS[run.target])}</button>`;
  return `<article class="model-card"><header><div><h3>${esc(TARGET_LABELS[run.target])}</h3><span class="status-pill ${esc(run.status)}">${esc(human(run.status))}</span></div><small>${shown(run.distinct_students)} students · ${shown(run.included_records)} records</small></header>${classes}${comparison}${warnings}${action}</article>`;
}

function modelsPage(data, models, state, staticMode) {
  const runs = latestRuns(models?.runs);
  const visible = state.modelTarget === "all" ? runs : runs.filter(run => run.target === state.modelTarget);
  return `${targetCards(runs, state.modelTarget)}<article class="viz-panel model-summary-panel"><header><div><h3>Predictive model results</h3><p>Course pass and active Badge models using Canvas behaviour and non-scored self-assessment completion.</p></div></header><div class="model-grid">${visible.map(run => modelCard(run, staticMode)).join("")}</div></article><details class="viz-panel wide notes"><summary>Definitions and limitations (${data.notes?.length || 0})</summary><ul>${(data.notes || []).map(note => `<li>${esc(note)}</li>`).join("")}</ul></details>`;
}

export function renderInsightsPage(data, models, ctx) {
  const state = ctx.state;
  ctx.metrics.classList.add("special-page");
  ctx.coverage.classList.add("special-page");
  ctx.tables.classList.add("special-page");
  ctx.notes.classList.add("special-page");
  ctx.metrics.innerHTML = "";
  ctx.coverage.innerHTML = `<div class="outcome-tabs" id="insightTabs"><button data-tab="summary" class="${state.insightsTab === "summary" ? "active" : ""}">Summary</button><button data-tab="suggestions" class="${state.insightsTab === "suggestions" ? "active" : ""}">Recommendations</button><button data-tab="models" class="${state.insightsTab === "models" ? "active" : ""}">Predictive models</button></div>`;
  ctx.tables.innerHTML = state.insightsTab === "summary" ? summaryPage(state)
    : state.insightsTab === "suggestions" ? recommendationsPage(data)
    : modelsPage(data, models, state, ctx.staticMode);
  ctx.notes.innerHTML = "";
  if (ctx.cohort) ctx.cohort.textContent = state.insightsTab === "models"
    ? "Population included: Model cohort pooled across teaching periods for the selected course"
    : "Scope: both reviewed courses and all nine teaching periods";
  document.querySelectorAll("#insightTabs button").forEach(button => button.onclick = () => {
    state.insightsTab = button.dataset.tab;
    renderInsightsPage(data, models, ctx);
  });
  document.querySelectorAll("[data-model-target]").forEach(button => button.onclick = () => {
    state.modelTarget = button.dataset.modelTarget;
    renderInsightsPage(data, models, ctx);
  });
  document.querySelectorAll("[data-retrain]").forEach(button => button.onclick = event => {
    state.modelTarget = button.dataset.retrain;
    ctx.retrain(event);
  });
  ctx.enhance?.();
}
