"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5", "#c4515c"];
const TARGET_LABELS = { AT1: "AT1", AT2: "AT2", weighted_final: "Overall course result", badge: "Badge" };
const QUESTIONS = {
  engagement_grade: {
    label: "Engagement and passing", question: "Is higher Canvas engagement associated with passing?",
    targets: ["AT1", "AT2", "weighted_final"], outcome: "passed", grouping: "passed",
    features: ["views", "participations"], metrics: ["mean_views", "mean_participations"]
  },
  page_category: {
    label: "Learning activity mix", question: "Which Canvas areas differ between students who passed and did not pass?",
    targets: ["AT1", "AT2", "weighted_final"], outcome: "passed", grouping: "passed",
    features: ["content_view_share", "assessment_view_share"], metrics: ["mean_content_view_share", "mean_assessment_view_share"]
  },
  timing_submission: {
    label: "When students started and submitted", question: "When during the course do students submit AT1 and AT2?",
    targets: ["AT1", "AT2"], outcome: "passed", grouping: "passed",
    features: ["submission_days_from_course_start", "first_activity_to_submission_days"],
    metrics: ["median_submission_days_from_course_start", "median_first_activity_to_submission_days"]
  },
  self_assessment: {
    label: "Self-assessment and passing", question: "Is self-assessment completion associated with passing?",
    targets: ["AT1", "AT2", "weighted_final"], outcome: "passed",
    features: ["self_assessment_completion_pct"], metrics: ["mean_outcome"]
  },
  badge_relationship: {
    label: "Behaviours linked to recorded Badges", question: "Which behaviours differ between students with and without a recorded Badge?",
    targets: ["badge"], outcome: "badge_observed", grouping: "outcome_group",
    features: ["views", "participations", "AT1_submitted", "AT2_submitted"],
    metrics: ["mean_views", "mean_participations", "mean_AT1_submitted", "mean_AT2_submitted"]
  }
};
const GROUP_LABELS = {
  below_70: "Below 70", "70_to_below_80": "70–<80", "80_and_above": "80 and above",
  valid: "Active Badge recorded", revoked_only: "Revoked Badge only", no_matched_award: "No Badge record found",
  needs_review: "Teaching period could not be confirmed", unknown: "Unknown", None: "Unknown", "0": "Not submitted", "1": "Submitted",
  none: "None", partial: "Partial", all: "All", score: "Score", submitted: "Submitted", passed: "Passed",
  submission_days_from_course_start: "Days from course start to submission",
  first_activity_to_submission_days: "Days from first Canvas activity to submission",
  median_submission_days_from_course_start: "Median days from course start",
  median_first_activity_to_submission_days: "Median days from first activity",
  content_view_share: "Content share of page views", assessment_view_share: "Assessment share of page views",
  participations: "Interactive actions", mean_participations: "Average interactive actions",
  macro_f1: "Overall class prediction quality", balanced_accuracy: "Balanced Accuracy",
  badge_observed: "Active Badge recorded"
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
    return `<button data-model-target="${target}" class="${selected === target ? "active" : ""}"><span>${esc(TARGET_LABELS[target])}</span><strong>${shown(valid, 0)} usable student records</strong><small class="status-pill ${esc(status)}">${esc(human(status))}</small></button>`;
  }).join("")}</div>`;
}

function questionNav(selected) {
  return `<div class="question-tabs">${Object.entries(QUESTIONS).map(([key, question], index) => `<button data-question-area="${key}" class="${selected === key ? "active" : ""}"><span>${index + 1}</span>${esc(question.label)}</button>`).join("")}</div>`;
}

function targetSelector(question, selected) {
  if (question.targets.length === 1) return '<span class="fixed-target">Outcome: Recorded Badge</span>';
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
  return `${human(row.dimensions.feature)} has the strongest observed ${strength(rho)} ${direction} relationship with ${human(row.dimensions.outcome)}.${uncertainty}`;
}

function forestPlot(rows) {
  if (!rows.length) return "";
  const position = number => `${Math.max(0, Math.min(100, (number + 1) * 50))}%`;
  const severalOutcomes = new Set(rows.map(row => row.dimensions.outcome)).size > 1;
  return `<div class="forest"><div class="forest-axis"><span>Negative relationship</span><span>No clear relationship</span><span>Positive relationship</span></div>${rows.map(row => {
    const rho = value(row, "spearman_rho"), low = value(row, "rho_ci_low"), high = value(row, "rho_ci_high"), n = value(row, "students");
    const label = severalOutcomes ? `${human(row.dimensions.feature)} · ${human(row.dimensions.outcome)}` : human(row.dimensions.feature);
    const plot = rho == null ? '<span class="unavailable">No stable estimate</span>' : `<div class="forest-track"><i class="zero"></i>${low == null || high == null ? "" : `<i class="interval" style="left:${position(low)};width:${Math.max(1, (high - low) * 50)}%"></i>`}<i class="estimate" style="left:${position(rho)}"></i></div>`;
    const plain=rho==null?"Unavailable":`${strength(rho)} ${rho>=0?"positive":"negative"}`;
    return `<div class="forest-row"><b title="${esc(label)}">${esc(label)}</b>${plot}<small>${esc(plain)} · n=${n ?? "NA"}</small></div>`;
  }).join("")}</div><div class="legend forest-legend"><span><i class="dot"></i>Observed relationship</span><span><i class="interval-key"></i>Uncertainty interval</span></div>`;
}

function formatProfile(metric, number) {
  if (number == null) return "NA";
  if (/share|submitted|rate|mean_outcome/.test(metric)) return `${(number * (/share/.test(metric) && Math.abs(number) > 1 ? 1 : 100)).toFixed(1)}%`;
  return number.toLocaleString("en-AU", { maximumFractionDigits: 1 });
}

function groupLabel(row) {
  const group=String(row.dimensions.group);
  if(row.dimensions.grouping==="passed") return group==="1"?"Passed":group==="0"?"Did not reach pass mark":"Result unavailable";
  return human(group);
}

function profileCharts(rows, metrics) {
  if (!rows.length) return "";
  return `<div class="mini-grid">${metrics.map(metric => {
    const points = rows.map(row => ({ label: groupLabel(row), value: value(row, metric) }));
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
    ...row, dimensions: { ...row.dimensions, grouping:"self_completion", group: row.dimensions.self_completion }
  }));
}

function coverageNote(rows, outcome) {
  const row = rows.find(item => item.dimensions.outcome === outcome);
  if (!row) return "Coverage is not available for this selection.";
  return `${value(row, "valid_outcomes") ?? "NA"} usable outcome records from ${value(row, "observed_records") ?? "NA"} observed records; ${value(row, "linked_engagement_records") ?? "NA"} also have Canvas activity data.`;
}

function confidenceText(rows) {
  const valid=rows.filter(row=>value(row,"spearman_rho")!=null);
  if(!valid.length) return "The available sample or variation is not sufficient for a stable relationship estimate.";
  const strongest=valid.sort((a,b)=>Math.abs(value(b,"spearman_rho"))-Math.abs(value(a,"spearman_rho")))[0];
  const n=value(strongest,"students"),low=value(strongest,"rho_ci_low"),high=value(strongest,"rho_ci_high");
  if(low==null||high==null) return `The relationship uses ${n??"an unavailable number of"} students, but the sample is too limited for a reliable uncertainty interval.`;
  return low<=0&&high>=0
    ? `The estimate uses ${n} students, but its uncertainty range includes no relationship. Treat the direction as tentative.`
    : `The estimate uses ${n} students and its uncertainty range keeps the same direction.`;
}

function meaningText(area) {
  return ({
    engagement_grade:"This identifies an observed engagement pattern. It does not show that increasing page views or actions will cause a student to pass.",
    page_category:"Differences show where each result group concentrated its Canvas activity. They do not measure the quality of study.",
    timing_submission:"The timing values are elapsed calendar days. They do not measure hours spent working on an assessment.",
    self_assessment:"A difference may help identify a useful learning pattern, but self-assessment completion is not a scored result.",
    badge_relationship:"Recorded Badge status can be affected by claiming, export and matching gaps, so it is not identical to course pass."
  })[area];
}

function exploration(data, state) {
  const tables = data.tables, area = state.insightArea, question = QUESTIONS[area];
  const selectedTarget = question.targets.includes(state.explorationTarget) ? state.explorationTarget : question.targets[0];
  state.explorationTarget = selectedTarget;
  const associations = relationshipRows(tables.associations || [], area, question);
  const comparisonGrouping = question.grouping;
  const comparisonRows = area === "self_assessment"
    ? selfAssessmentRows(tables.self_assessment_association || [], question.outcome)
    : (tables.behavior_by_outcome || []).filter(row => row.dimensions.grouping === comparisonGrouping);
  const comparable = comparisonRows.filter(row => question.metrics.some(metric => value(row, metric) != null));
  const comparison = comparable.length > 1 ? profileCharts(comparisonRows, question.metrics)
    : '<p class="empty">A group comparison is not available because fewer than two groups have usable values.</p>';
  const evidence=["page_category","timing_submission","self_assessment","badge_relationship"].includes(area)
    ? panel("Evidence", area==="timing_submission"?"Bars show median elapsed days for each result group.":"Bars compare aggregate student groups.",comparison)
    : panel("Evidence","Position shows the direction and strength of each observed relationship. Technical values remain in Supporting figures.",forestPlot(associations));
  return `<section class="insight-question-header"><div><span>Exploration question</span><h2>${esc(question.question)}</h2><p>Compatible teaching periods are combined to preserve the available sample.</p></div>${targetSelector(question, selectedTarget)}</section>
    <article class="key-finding"><span>Main finding</span><strong>${esc(keyFinding(associations))}</strong></article>
    ${evidence}
    <div class="report-notes">
      <article class="report-meaning"><strong>What it may mean</strong><p>${esc(meaningText(area))}</p></article>
      <article class="report-confidence"><strong>Confidence</strong><p>${esc(confidenceText(associations))}</p></article>
      <article class="report-limitation"><strong>Data limitation</strong><p>${esc(coverageNote(tables.analysis_coverage || [], question.outcome))}</p></article>
    </div>
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
  ctx.coverage.innerHTML = `<div class="outcome-tabs" id="insightTabs"><button data-tab="exploration" class="${state.insightsTab === "exploration" ? "active" : ""}">Exploration</button><button data-tab="models" class="${state.insightsTab === "models" ? "active" : ""}">Predictive models</button></div>`;
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
