"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5", "#c4515c"];
const TARGET_LABELS = { AT1: "AT1", AT2: "AT2", weighted_final: "Weighted final", badge: "Badge" };
const AREA_LABELS = {
  engagement_grade: "Engagement and grades", page_category: "Page categories",
  timing_submission: "Contact timing", self_assessment: "Self-assessment",
  badge_relationship: "Badge relationship"
};
const GROUP_LABELS = {
  below_70: "Below 70", "70_to_below_80": "70–<80", "80_and_above": "80 and above",
  valid: "Valid Badge", revoked_only: "Revoked only", no_matched_award: "No matched award",
  needs_review: "Needs review", unknown: "Unknown", None: "Unknown", "0": "Not submitted", "1": "Submitted",
  none: "None", partial: "Partial", all: "All"
};

const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[c]);
const human = value => GROUP_LABELS[value] || TARGET_LABELS[value] || AREA_LABELS[value] ||
  String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const value = (row, key) => typeof row?.metrics?.[key]?.value === "number" ? row.metrics[key].value : null;
const shown = (metric, digits = 1) => metric?.value == null || metric?.suppressed
  ? '<span class="unavailable">Not available</span>'
  : Number(metric.value).toLocaleString("en-AU", { maximumFractionDigits: digits });

function table(rows, title = "View data") {
  if (!rows?.length) return "";
  const dimensions = [...new Set(rows.flatMap(row => Object.keys(row.dimensions || {})))];
  const metrics = [...new Set(rows.flatMap(row => Object.keys(row.metrics || {})))];
  return `<details><summary>${esc(title)} (${rows.length} rows)</summary><div class="table-wrap"><table><thead><tr><th>Item</th>${dimensions.map(key => `<th>${esc(human(key))}</th>`).join("")}${metrics.map(key => `<th>${esc(human(key))}</th>`).join("")}</tr></thead><tbody>${rows.map(row => `<tr><td>${esc(human(row.label))}</td>${dimensions.map(key => `<td>${esc(human(row.dimensions?.[key] ?? "—"))}</td>`).join("")}${metrics.map(key => `<td>${shown(row.metrics?.[key], 3)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}

function panel(title, subtitle, body, rows = [], wide = true) {
  return `<article class="viz-panel${wide ? " wide" : ""}"><header><div><h3>${esc(title)}</h3>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div></header>${body || '<p class="empty">No data available for this selection.</p>'}${table(rows)}</article>`;
}

function primaryCoverage(rows, target) {
  const outcome = target === "badge" ? "badge_observed" : "score";
  return rows.find(row => row.dimensions?.target === target && row.dimensions?.outcome === outcome);
}

function targetCards(options, coverage, runs, selected) {
  return `<div class="target-toolbar"><button data-target="all" class="${selected === "all" ? "active" : ""}">Course overview</button></div><div class="insight-targets">${options.map(option => {
    const target = option.dimensions.target, run = runs.find(item => item.target === target);
    const covered = primaryCoverage(coverage, target), valid = covered?.metrics?.valid_outcomes || run?.included_records;
    const state = run?.status || "never_trained";
    return `<button data-target="${target}" class="${selected === target ? "active" : ""}"><span>${esc(TARGET_LABELS[target])}</span><strong>${shown(valid, 0)} valid records</strong><small class="status-pill ${esc(state)}">${esc(human(state))}</small></button>`;
  }).join("")}</div>`;
}

function coverageFunnel(rows) {
  if (!rows.length) return "";
  return `<div class="coverage-funnels">${rows.map(row => {
    const observed = value(row, "observed_records"), valid = value(row, "valid_outcomes"), linked = value(row, "linked_engagement_records");
    const width = count => observed ? Math.max(2, count / observed * 100) : 0;
    return `<section><h4>${esc(TARGET_LABELS[row.dimensions.target])}</h4><div><span>Observed <b>${observed ?? "NA"}</b></span><i style="width:${width(observed)}%;background:${COLORS[0]}"></i></div><div><span>Valid outcome <b>${valid ?? "NA"}</b></span><i style="width:${width(valid)}%;background:${COLORS[2]}"></i></div><div><span>Linked engagement <b>${linked ?? "NA"}</b></span><i style="width:${width(linked)}%;background:${COLORS[1]}"></i></div></section>`;
  }).join("")}</div><div class="legend"><span><i style="background:${COLORS[0]}"></i>Observed</span><span><i style="background:${COLORS[2]}"></i>Valid outcome</span><span><i style="background:${COLORS[1]}"></i>Linked engagement</span></div>`;
}

function questionCards(rows) {
  return `<div class="question-grid">${rows.map(row => `<article><b>${esc(AREA_LABELS[row.dimensions.analysis_area])}</b><p>${esc(row.dimensions.result)}</p></article>`).join("")}</div>`;
}

function forestPlot(rows) {
  if (!rows.length) return "";
  const position = number => `${Math.max(0, Math.min(100, (number + 1) * 50))}%`;
  return `<div class="forest"><div class="forest-axis"><span>−1 negative</span><span>0</span><span>+1 positive</span></div>${rows.map(row => {
    const rho = value(row, "spearman_rho"), low = value(row, "rho_ci_low"), high = value(row, "rho_ci_high"), adjusted = value(row, "within_offering_rank_r"), n = value(row, "students");
    const estimate = rho == null ? '<span class="unavailable">No stable estimate</span>' : `<div class="forest-track"><i class="zero"></i>${low == null || high == null ? "" : `<i class="interval" style="left:${position(low)};width:${Math.max(1, (high-low)*50)}%"></i>`}<i class="estimate" style="left:${position(rho)}"><span>${rho.toFixed(2)}</span></i></div>`;
    return `<div class="forest-row"><b>${esc(human(row.dimensions.feature))}</b>${estimate}<small>Adjusted: ${adjusted == null ? "NA" : adjusted.toFixed(2)} · n=${n ?? "NA"}</small></div>`;
  }).join("")}</div><div class="legend forest-legend"><span><i class="dot"></i>Spearman relationship</span><span><i class="interval-key"></i>95% uncertainty interval</span><span>Adjusted = within-offering rank relationship</span></div>`;
}

function formatProfile(metric, number) {
  if (number == null) return "NA";
  if (/share|submitted|rate/.test(metric)) return `${(number * 100).toFixed(1)}%`;
  return number.toLocaleString("en-AU", { maximumFractionDigits: 1 });
}

function profileCharts(rows, metrics) {
  return `<div class="mini-grid">${metrics.map(metric => {
    const points = rows.map(row => ({ label: human(row.dimensions.group), value: value(row, metric) }));
    const valid = points.map(point => point.value).filter(number => number != null);
    if (!valid.length) return `<section class="mini-viz"><h4>${esc(human(metric))}</h4><p class="empty">Not available</p></section>`;
    const min = Math.min(0, ...valid), max = Math.max(0, ...valid), span = max-min || 1, zero = (0-min)/span*100;
    return `<section class="mini-viz"><h4>${esc(human(metric))}</h4><div class="profile-bars">${points.map(point => {
      if (point.value == null) return `<div><span>${esc(point.label)}</span><div></div><b>NA</b></div>`;
      const end=(point.value-min)/span*100, left=Math.min(zero,end), width=Math.max(1,Math.abs(end-zero));
      return `<div><span>${esc(point.label)}</span><div class="profile-track"><i class="profile-zero" style="left:${zero}%"></i><i style="left:${left}%;width:${width}%"></i></div><b>${formatProfile(metric,point.value)}</b></div>`;
    }).join("")}</div></section>`;
  }).join("")}</div>`;
}

function selfAssessment(rows, outcome) {
  const selected = rows.filter(row => row.dimensions.outcome === outcome);
  const metric = outcome === "score" ? "mean_score_pct" : outcome === "submission_days_from_deadline" ? "mean_days_from_deadline" : "mean_outcome_rate";
  const normalized = selected.map(row => ({...row, dimensions:{...row.dimensions, group:row.dimensions.self_completion}, metrics:{...row.metrics,[metric]:row.metrics.mean_outcome}}));
  return profileCharts(normalized, [metric]);
}

function areaMetrics(area) {
  return {
    engagement_grade: ["mean_views", "mean_participations"],
    page_category: ["mean_content_view_share", "mean_assessment_view_share"],
    timing_submission: ["mean_first_contact_days_from_start", "mean_first_contact_days_from_deadline"],
    badge_relationship: ["mean_views", "mean_participations", "mean_AT1_submitted", "mean_AT2_submitted"]
  }[area] || [];
}

function modelCard(run, selectedTarget, staticMode) {
  const counts = Object.entries(run.class_counts || {}), total = counts.reduce((sum,[,metric]) => sum + (metric.value || 0), 0);
  const candidates = Object.entries(run.candidates || {});
  const classes = counts.length ? `<div class="model-classes"><div>${counts.map(([label,metric],index) => `<i style="width:${total ? metric.value/total*100 : 0}%;background:${COLORS[index]}" title="${esc(human(label))}: ${metric.value}"></i>`).join("")}</div><div class="legend">${counts.map(([label,metric],index) => `<span><i style="background:${COLORS[index]}"></i>${esc(human(label))} ${metric.value}</span>`).join("")}</div></div>` : "";
  const comparison = candidates.length ? `<div class="model-comparison">${candidates.map(([name,metrics]) => `<section class="${run.selected_model===name?"selected":""}"><h4>${esc(human(name))}${run.selected_model===name?" · Selected":""}</h4>${["macro_f1","balanced_accuracy"].map((key,index) => `<div><span>${esc(human(key))}</span><i><b style="width:${metrics[key]*100}%;background:${COLORS[index]}"></b></i><strong>${metrics[key].toFixed(3)}</strong></div>`).join("")}</section>`).join("")}</div><div class="legend"><span><i style="background:${COLORS[0]}"></i>Macro F1</span><span><i style="background:${COLORS[1]}"></i>Balanced Accuracy</span></div>` : `<p class="model-reason">${esc(human(run.reason || "No candidate model could be evaluated"))}</p>`;
  const warnings = run.warnings?.length ? `<p class="model-warning">${run.warnings.map(human).join(" · ")}</p>` : "";
  const action = selectedTarget !== run.target ? "" : staticMode
    ? `<button class="action" disabled title="Open the internal live application to retrain">Saved snapshot</button>`
    : `<button class="action" data-retrain="${run.target}">Retrain ${esc(TARGET_LABELS[run.target])}</button>`;
  return `<article class="model-card"><header><div><h3>${esc(TARGET_LABELS[run.target])}</h3><span class="status-pill ${esc(run.status)}">${esc(human(run.status))}</span></div><small>${shown(run.distinct_students,0)} students · ${shown(run.included_records,0)} records</small></header>${classes}${comparison}${warnings}${action}</article>`;
}

function exploration(data, state) {
  const t=data.tables, target=state.target;
  if (target === "all") {
    const primary = Object.keys(TARGET_LABELS).map(key => primaryCoverage(t.analysis_coverage||[], key)).filter(Boolean);
    return `<div class="viz-grid">${panel("Analysis coverage","Each funnel shows the records available for the primary outcome of a target",coverageFunnel(primary),primary)}${panel("Exploration questions","Choose a target above to open its detailed aggregate analysis",questionCards(t.analysis_questions||[]),t.analysis_questions||[])}</div>`;
  }
  const questions=t.analysis_questions||[], available = target === "badge" ? ["badge_relationship"] : ["engagement_grade","page_category","timing_submission","self_assessment"];
  if (!available.includes(state.insightArea)) state.insightArea=available[0];
  const area=state.insightArea, areaRows=(t.associations||[]).filter(row=>row.dimensions.analysis_area===area);
  const outcomes=[...new Set(areaRows.map(row=>row.dimensions.outcome))];
  const defaults={engagement_grade:"score",page_category:"score",timing_submission:"submitted",self_assessment:"score",badge_relationship:"badge_observed"};
  if (!outcomes.includes(state.insightOutcome)) state.insightOutcome=outcomes.includes(defaults[area])?defaults[area]:outcomes[0];
  const outcome=state.insightOutcome, associations=areaRows.filter(row=>row.dimensions.outcome===outcome);
  const groupName=target==="badge"?"outcome_group":outcome==="score"||target==="weighted_final"?"grade_band":"submitted";
  const groups=(t.behavior_by_outcome||[]).filter(row=>row.dimensions.grouping===groupName);
  const question=questions.find(row=>row.dimensions.analysis_area===area);
  const controls=`<div class="chips" id="insightAreas">${available.map(key=>`<button data-area="${key}" class="${area===key?"active":""}">${esc(AREA_LABELS[key])}</button>`).join("")}</div><label class="insight-outcome">Outcome<select id="insightOutcome">${outcomes.map(key=>`<option value="${key}" ${outcome===key?"selected":""}>${esc(human(key))}</option>`).join("")}</select></label>`;
  const coverage=(t.analysis_coverage||[]).filter(row=>row.dimensions.outcome===outcome);
  const body=[panel(question?.label||AREA_LABELS[area],question?.dimensions.result||"",controls,[]),panel("Observed relationship","Dots show Spearman rank relationships; intervals crossing zero indicate an uncertain direction",forestPlot(associations),associations),panel("Group comparison","Direct labels identify each group; timing values use zero as the deadline/start reference",area==="self_assessment"?selfAssessment(t.self_assessment_association||[],outcome):profileCharts(groups,areaMetrics(area)),area==="self_assessment"?(t.self_assessment_association||[]).filter(row=>row.dimensions.outcome===outcome):groups),panel("Analysis coverage","Observed, valid and Engagement-linked records for this outcome",coverageFunnel(coverage),coverage)].join("");
  return `<div class="viz-grid">${body}</div>`;
}

export function renderInsightsPage(data, models, ctx) {
  const t=data.tables, state=ctx.state, runs=models?.runs||[];
  ctx.metrics.classList.add("special-page"); ctx.coverage.classList.add("special-page");
  ctx.tables.classList.add("special-page"); ctx.notes.classList.add("special-page");
  ctx.metrics.innerHTML=targetCards(t.analysis_options||[],t.analysis_coverage||[],runs,state.target);
  ctx.coverage.innerHTML=`<div class="outcome-tabs" id="insightTabs"><button data-tab="exploration" class="${state.insightsTab==="exploration"?"active":""}">Exploration</button><button data-tab="models" class="${state.insightsTab==="models"?"active":""}">Models</button></div>`;
  const order=Object.keys(TARGET_LABELS), visibleRuns=(state.target==="all"?runs:runs.filter(run=>run.target===state.target))
    .sort((a,b)=>order.indexOf(a.target)-order.indexOf(b.target));
  ctx.tables.innerHTML=state.insightsTab==="models"?`<div class="model-grid">${visibleRuns.map(run=>modelCard(run,state.target,ctx.staticMode)).join("")}</div>`:exploration(data,state);
  ctx.notes.innerHTML=`<details class="viz-panel wide notes"><summary>Definitions and limitations (${data.notes?.length||0})</summary><ul>${(data.notes||[]).map(note=>`<li>${esc(note)}</li>`).join("")}</ul></details>`;
  document.querySelectorAll("[data-target]").forEach(button=>button.onclick=()=>{state.target=button.dataset.target;state.insightArea=state.target==="badge"?"badge_relationship":"engagement_grade";state.insightOutcome="";ctx.reload();});
  document.querySelectorAll("#insightTabs button").forEach(button=>button.onclick=()=>{state.insightsTab=button.dataset.tab;renderInsightsPage(data,models,ctx);});
  document.querySelectorAll("#insightAreas button").forEach(button=>button.onclick=()=>{state.insightArea=button.dataset.area;state.insightOutcome="";renderInsightsPage(data,models,ctx);});
  document.querySelector("#insightOutcome")?.addEventListener("change",event=>{state.insightOutcome=event.target.value;renderInsightsPage(data,models,ctx);});
  document.querySelector("[data-retrain]")?.addEventListener("click",ctx.retrain);
}
