"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5", "#c4515c"];
const TARGET_LABELS = { AT1: "AT1", AT2: "AT2", weighted_final: "Weighted final", badge: "Badge" };
const QUESTIONS = {
  engagement_grade: {
    label: "Engagement and grades", question: "How are views and participations related to assessment results?",
    targets: ["AT1", "AT2", "weighted_final"], outcome: "score", grouping: "grade_band",
    features: ["views", "participations"], metrics: ["mean_views", "mean_participations"]
  },
  page_category: {
    label: "Page categories", question: "How is contact with content and assessment pages related to grades and submission?",
    targets: ["AT1", "AT2", "weighted_final"], outcome: "score", grouping: "submitted",
    features: ["content_view_share", "assessment_view_share"], metrics: ["mean_content_view_share", "mean_assessment_view_share"]
  },
  timing_submission: {
    label: "Contact timing", question: "How is first contact timing related to submission, lateness and grades?",
    targets: ["AT1", "AT2"], outcome: "submitted", grouping: "submitted",
    features: ["first_contact_days_from_start", "first_contact_days_from_deadline"],
    outcomes: ["submitted", "late_flag", "score"], metrics: ["mean_first_contact_days_from_start", "mean_first_contact_days_from_deadline"]
  },
  self_assessment: {
    label: "Self-assessment", question: "How does self-assessment completion differ across scored-assessment outcomes?",
    targets: ["AT1", "AT2", "weighted_final"], outcome: "score",
    features: ["self_assessment_completion_pct"], metrics: ["mean_score_pct"]
  },
  badge_relationship: {
    label: "Badge relationship", question: "How do engagement and submission patterns differ by Badge outcome?",
    targets: ["badge"], outcome: "badge_observed", grouping: "outcome_group",
    features: ["views", "participations", "AT1_submitted", "AT2_submitted"],
    metrics: ["mean_views", "mean_participations", "mean_AT1_submitted", "mean_AT2_submitted"]
  }
};
const GROUP_LABELS = {
  below_70: "Below 70", "70_to_below_80": "70–<80", "80_and_above": "80 and above",
  valid: "Valid Badge", revoked_only: "Revoked only", no_matched_award: "No matched award",
  needs_review: "Needs review", unknown: "Unknown", None: "Unknown", "0": "Not submitted", "1": "Submitted",
  none: "None", partial: "Partial", all: "All", score: "Score", submitted: "Submitted",
  late_flag: "Late submission", badge_observed: "Valid Badge"
};

const esc = item => String(item ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[character]);
const human = item => GROUP_LABELS[item] || TARGET_LABELS[item] || QUESTIONS[item]?.label ||
  String(item ?? "").replaceAll("_", " ").replace(/\b\w/g, character => character.toUpperCase());
const value = (row, key) => typeof row?.metrics?.[key]?.value === "number" ? row.metrics[key].value : null;
const shown = (metric, digits = 1) => metric?.value == null || metric?.suppressed
  ? '<span class="unavailable">Not available</span>'
  : Number(metric.value).toLocaleString("en-AU", { maximumFractionDigits: digits });

function dataTable(rows) {
  if (!rows.length) return "";
  const dimensions = [...new Set(rows.flatMap(row => Object.keys(row.dimensions || {})))];
  const metrics = [...new Set(rows.flatMap(row => Object.keys(row.metrics || {})))];
  return `<details class="insight-data"><summary>View supporting data (${rows.length} rows)</summary><div class="table-wrap"><table><thead><tr><th>Item</th>${dimensions.map(key => `<th>${esc(human(key))}</th>`).join("")}${metrics.map(key => `<th>${esc(human(key))}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr><td>${esc(human(row.label))}</td>${dimensions.map(key => `<td>${esc(human(row.dimensions?.[key] ?? "—"))}</td>`).join("")}${metrics.map(key => `<td>${shown(row.metrics?.[key], 3)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}

function panel(title, subtitle, body) {
  return `<article class="viz-panel"><header><div><h3>${esc(title)}</h3>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div></header>${body || '<p class="empty">No data available for this selection.</p>'}</article>`;
}

function targetCards(options, coverage, runs, selected) {
  return `<div class="target-toolbar"><button data-model-target="all" class="${selected === "all" ? "active" : ""}">All models</button></div><div class="insight-targets">${options.map(option => {
    const target = option.dimensions.target, run = runs.find(item => item.target === target);
    const covered = coverage.find(row => row.dimensions?.target === target && row.dimensions?.outcome === (target === "badge" ? "badge_observed" : "score"));
    const valid = covered?.metrics?.valid_outcomes || run?.included_records, status = run?.status || "never_trained";
    return `<button data-model-target="${target}" class="${selected === target ? "active" : ""}"><span>${esc(TARGET_LABELS[target])}</span><strong>${shown(valid, 0)} valid records</strong><small class="status-pill ${esc(status)}">${esc(human(status))}</small></button>`;
  }).join("")}</div>`;
}

function questionNav(selected) {
  return `<div class="question-tabs">${Object.entries(QUESTIONS).map(([key, question], index) => `<button data-question-area="${key}" class="${selected === key ? "active" : ""}"><span>${index + 1}</span>${esc(question.label)}</button>`).join("")}</div>`;
}

function targetSelector(question, selected) {
  if (question.targets.length === 1) return `<span class="fixed-target">Target: ${esc(TARGET_LABELS[question.targets[0]])}</span>`;
  return `<label class="insight-target-select">Assessment<select id="explorationTarget">${question.targets.map(target => `<option value="${target}" ${selected === target ? "selected" : ""}>${esc(TARGET_LABELS[target])}</option>`).join("")}</select></label>`;
}

function relationshipRows(rows, area, question) {
  return rows.filter(row => row.dimensions.analysis_area === area && question.features.includes(row.dimensions.feature) &&
    (question.outcomes || [question.outcome]).includes(row.dimensions.outcome));
}

function strength(number) {
  const magnitude = Math.abs(number);
  return magnitude < .1 ? "very weak" : magnitude < .3 ? "weak" : magnitude < .5 ? "moderate" : "strong";
}

function keyFinding(rows) {
  const valid = rows.filter(row => value(row, "spearman_rho") != null);
  if (!valid.length) return "No stable correlation estimate is available for this selection.";
  const row = valid.sort((a, b) => Math.abs(value(b, "spearman_rho")) - Math.abs(value(a, "spearman_rho")))[0];
  const rho = value(row, "spearman_rho"), low = value(row, "rho_ci_low"), high = value(row, "rho_ci_high");
  const direction = rho >= 0 ? "positive" : "negative";
  const uncertainty = low != null && high != null && low <= 0 && high >= 0
    ? " The uncertainty interval crosses zero, so the direction is not stable." : "";
  return `${human(row.dimensions.feature)} has the strongest observed ${strength(rho)} ${direction} relationship with ${human(row.dimensions.outcome)} (ρ ${rho.toFixed(2)}, n=${value(row, "students") ?? "NA"}).${uncertainty}`;
}

function forestPlot(rows) {
  if (!rows.length) return "";
  const position = number => `${Math.max(0, Math.min(100, (number + 1) * 50))}%`;
  const severalOutcomes = new Set(rows.map(row => row.dimensions.outcome)).size > 1;
  return `<div class="forest"><div class="forest-axis"><span>−1 negative</span><span>0</span><span>+1 positive</span></div>${rows.map(row => {
    const rho = value(row, "spearman_rho"), low = value(row, "rho_ci_low"), high = value(row, "rho_ci_high"), n = value(row, "students");
    const label = severalOutcomes ? `${human(row.dimensions.feature)} · ${human(row.dimensions.outcome)}` : human(row.dimensions.feature);
    const plot = rho == null ? '<span class="unavailable">No stable estimate</span>' : `<div class="forest-track"><i class="zero"></i>${low == null || high == null ? "" : `<i class="interval" style="left:${position(low)};width:${Math.max(1, (high - low) * 50)}%"></i>`}<i class="estimate" style="left:${position(rho)}"><span>${rho.toFixed(2)}</span></i></div>`;
    return `<div class="forest-row"><b title="${esc(label)}">${esc(label)}</b>${plot}<small>n=${n ?? "NA"}</small></div>`;
  }).join("")}</div><div class="legend forest-legend"><span><i class="dot"></i>Spearman ρ</span><span><i class="interval-key"></i>95% uncertainty interval</span></div>`;
}

function formatProfile(metric, number) {
  if (number == null) return "NA";
  if (/share|submitted|rate/.test(metric)) return `${(number * (/share/.test(metric) && Math.abs(number) > 1 ? 1 : 100)).toFixed(1)}%`;
  return number.toLocaleString("en-AU", { maximumFractionDigits: 1 });
}

function profileCharts(rows, metrics) {
  if (!rows.length) return "";
  return `<div class="mini-grid">${metrics.map(metric => {
    const points = rows.map(row => ({ label: human(row.dimensions.group), value: value(row, metric) }));
    const valid = points.map(point => point.value).filter(number => number != null);
    if (!valid.length) return `<section class="mini-viz"><h4>${esc(human(metric))}</h4><p class="empty">Not available</p></section>`;
    const min = Math.min(0, ...valid), max = Math.max(0, ...valid), span = max - min || 1, zero = (0 - min) / span * 100;
    return `<section class="mini-viz"><h4>${esc(human(metric))}</h4><div class="profile-bars">${points.map(point => {
      if (point.value == null) return `<div><span>${esc(point.label)}</span><div></div><b>NA</b></div>`;
      const end = (point.value - min) / span * 100, left = Math.min(zero, end), width = Math.max(1, Math.abs(end - zero));
      return `<div><span>${esc(point.label)}</span><div class="profile-track"><i class="profile-zero" style="left:${zero}%"></i><i style="left:${left}%;width:${width}%"></i></div><b>${formatProfile(metric, point.value)}</b></div>`;
    }).join("")}</div></section>`;
  }).join("")}</div>`;
}

function selfAssessmentRows(rows, outcome) {
  return rows.filter(row => row.dimensions.outcome === outcome).map(row => ({
    ...row, dimensions: { ...row.dimensions, group: row.dimensions.self_completion },
    metrics: { ...row.metrics, mean_score_pct: row.metrics.mean_outcome }
  }));
}

function coverageNote(rows, outcome) {
  const row = rows.find(item => item.dimensions.outcome === outcome);
  if (!row) return "Coverage is not available for this selection.";
  return `${value(row, "valid_outcomes") ?? "NA"} valid outcomes from ${value(row, "observed_records") ?? "NA"} observed records; ${value(row, "linked_engagement_records") ?? "NA"} have linked engagement. Correlations are descriptive and intervals crossing zero indicate uncertain direction.`;
}

function exploration(data, state) {
  const tables = data.tables, area = state.insightArea, question = QUESTIONS[area];
  const selectedTarget = question.targets.includes(state.explorationTarget) ? state.explorationTarget : question.targets[0];
  state.explorationTarget = selectedTarget;
  const associations = relationshipRows(tables.associations || [], area, question);
  const comparisonGrouping = area === "page_category" && selectedTarget === "weighted_final" ? "grade_band" : question.grouping;
  const comparisonRows = area === "self_assessment"
    ? selfAssessmentRows(tables.self_assessment_association || [], question.outcome)
    : (tables.behavior_by_outcome || []).filter(row => row.dimensions.grouping === comparisonGrouping);
  const comparable = comparisonRows.filter(row => question.metrics.some(metric => value(row, metric) != null));
  const comparison = comparable.length > 1 ? profileCharts(comparisonRows, question.metrics)
    : '<p class="empty">A group comparison is not available because fewer than two groups have usable values.</p>';
  return `<section class="insight-question-header"><div><span>Exploration question</span><h2>${esc(question.question)}</h2><p>All compatible offerings in the selected course are pooled to preserve the available sample.</p></div>${targetSelector(question, selectedTarget)}</section>
    <article class="key-finding"><span>Key finding</span><strong>${esc(keyFinding(associations))}</strong></article>
    <div class="simple-insight-grid">
      ${panel("Observed relationship", "Spearman ρ ranges from −1 to +1; values nearer either end indicate a stronger ranked relationship.", forestPlot(associations))}
      ${panel("Group comparison", area === "timing_submission" ? "Zero marks the course start or assignment deadline; negative values are earlier." : "Bars compare aggregate group averages.", comparison)}
    </div>
    <p class="coverage-summary">${esc(coverageNote(tables.analysis_coverage || [], question.outcome))}</p>
    ${dataTable([...associations, ...comparisonRows])}`;
}

function modelCard(run, selectedTarget, staticMode) {
  const counts = Object.entries(run.class_counts || {}), total = counts.reduce((sum, [, metric]) => sum + (metric.value || 0), 0);
  const candidates = Object.entries(run.candidates || {});
  const classes = counts.length ? `<div class="model-classes"><div>${counts.map(([label, metric], index) => `<i style="width:${total ? metric.value / total * 100 : 0}%;background:${COLORS[index]}" title="${esc(human(label))}: ${metric.value}"></i>`).join("")}</div><div class="legend">${counts.map(([label, metric], index) => `<span><i style="background:${COLORS[index]}"></i>${esc(human(label))} ${metric.value}</span>`).join("")}</div></div>` : "";
  const comparison = candidates.length ? `<div class="model-comparison">${candidates.map(([name, metrics]) => `<section class="${run.selected_model === name ? "selected" : ""}"><h4>${esc(human(name))}${run.selected_model === name ? " · Selected" : ""}</h4>${["macro_f1", "balanced_accuracy"].map((key, index) => `<div><span>${esc(human(key))}</span><i><b style="width:${metrics[key] * 100}%;background:${COLORS[index]}"></b></i><strong>${metrics[key].toFixed(3)}</strong></div>`).join("")}</section>`).join("")}</div><div class="legend"><span><i style="background:${COLORS[0]}"></i>Macro F1</span><span><i style="background:${COLORS[1]}"></i>Balanced Accuracy</span></div>` : `<p class="model-reason">${esc(human(run.reason || "No candidate model could be evaluated"))}</p>`;
  const warnings = run.warnings?.length ? `<p class="model-warning">${run.warnings.map(human).join(" · ")}</p>` : "";
  const action = selectedTarget !== run.target ? "" : staticMode
    ? '<button class="action" disabled title="Open the internal live application to retrain">Saved snapshot</button>'
    : `<button class="action" data-retrain="${run.target}">Retrain ${esc(TARGET_LABELS[run.target])}</button>`;
  return `<article class="model-card"><header><div><h3>${esc(TARGET_LABELS[run.target])}</h3><span class="status-pill ${esc(run.status)}">${esc(human(run.status))}</span></div><small>${shown(run.distinct_students, 0)} students · ${shown(run.included_records, 0)} records</small></header>${classes}${comparison}${warnings}${action}</article>`;
}

export function renderInsightsPage(data, models, ctx) {
  const tables = data.tables, state = ctx.state, runs = models?.runs || [];
  ctx.metrics.classList.add("special-page"); ctx.coverage.classList.add("special-page");
  ctx.tables.classList.add("special-page"); ctx.notes.classList.add("special-page");
  ctx.coverage.innerHTML = `<div class="outcome-tabs" id="insightTabs"><button data-tab="exploration" class="${state.insightsTab === "exploration" ? "active" : ""}">Exploration</button><button data-tab="models" class="${state.insightsTab === "models" ? "active" : ""}">Models</button></div>`;
  if (state.insightsTab === "exploration") {
    ctx.metrics.innerHTML = questionNav(state.insightArea);
    ctx.tables.innerHTML = exploration(data, state);
  } else {
    ctx.metrics.innerHTML = targetCards(tables.analysis_options || [], tables.analysis_coverage || [], runs, state.modelTarget);
    const order = Object.keys(TARGET_LABELS);
    const visible = (state.modelTarget === "all" ? runs : runs.filter(run => run.target === state.modelTarget))
      .sort((a, b) => order.indexOf(a.target) - order.indexOf(b.target));
    ctx.tables.innerHTML = `<div class="model-grid">${visible.map(run => modelCard(run, state.modelTarget, ctx.staticMode)).join("")}</div>`;
  }
  ctx.notes.innerHTML = `<details class="viz-panel wide notes"><summary>Definitions and limitations (${data.notes?.length || 0})</summary><ul>${(data.notes || []).map(note => `<li>${esc(note)}</li>`).join("")}</ul></details>`;
  document.querySelectorAll("#insightTabs button").forEach(button => button.onclick = () => {
    state.insightsTab = button.dataset.tab; renderInsightsPage(data, models, ctx);
  });
  document.querySelectorAll("[data-question-area]").forEach(button => button.onclick = () => {
    state.insightArea = button.dataset.questionArea;
    const allowed = QUESTIONS[state.insightArea].targets;
    if (!allowed.includes(state.explorationTarget)) state.explorationTarget = allowed[0];
    ctx.reload();
  });
  document.querySelector("#explorationTarget")?.addEventListener("change", event => {
    state.explorationTarget = event.target.value; ctx.reload();
  });
  document.querySelectorAll("[data-model-target]").forEach(button => button.onclick = () => {
    state.modelTarget = button.dataset.modelTarget; renderInsightsPage(data, models, ctx);
  });
  document.querySelector("[data-retrain]")?.addEventListener("click", ctx.retrain);
}
