"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5", "#c4515c", "#4b8795", "#768399"];
const BAND_LABELS = {
  below_70: "Below 70", "70_to_below_80": "70–<80", "80_and_above": "80 and above",
  unknown: "Unknown", yes: "Yes", no: "No", submitted: "Submitted", unsubmitted: "Unsubmitted",
  graded: "Graded", excused: "Excused", not_late: "Not late", no_observed_submission: "No submission"
};
const CATEGORY_COLORS = {
  submitted: "#438a69", graded: "#2878b5", unsubmitted: "#8793a5", missing: "#c4515c",
  excused: "#8057a5", valid: "#438a69", revoked_only: "#c4515c",
  needs_review: "#d9792b", no_matched_award: "#8793a5", unknown: "#768399"
};

const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
})[c]);
const human = value => BAND_LABELS[value] || String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, c => c.toUpperCase());
const number = (row, key) => typeof row?.metrics?.[key]?.value === "number" ? row.metrics[key].value : null;
const shown = (metric, digits = 1, suffix = "") => {
  if (!metric || metric.suppressed || metric.value == null) return '<span class="unavailable">Not available</span>';
  return typeof metric.value === "number"
    ? `${metric.value.toLocaleString("en-AU", { maximumFractionDigits: digits })}${suffix}` : esc(metric.value);
};
const shortOffering = code => {
  const match = String(code || "").trim().match(/^(?:[A-Z0-9]+[ _-]+)?(\d{4})[ _-]+([A-Z]{3})[ _-]+PAR[ _-]+(\d+)$/i);
  return match ? `${match[1]} ${match[2].toUpperCase()} PAR ${match[3]}` : String(code || "Unknown");
};
const rowLabel = row => {
  const raw = row.dimensions?.offering || row.label || row.key;
  const compact = shortOffering(raw);
  return compact !== String(raw || "Unknown") ? compact : human(raw);
};

function details(rows, title = "View data") {
  if (!rows?.length) return "";
  const dimensions = [...new Set(rows.flatMap(row => Object.keys(row.dimensions || {})))];
  const metrics = [...new Set(rows.flatMap(row => Object.keys(row.metrics || {})))];
  return `<details><summary>${esc(title)} (${rows.length} rows)</summary><div class="table-wrap"><table><thead><tr><th>Item</th>${dimensions.map(key => `<th>${esc(human(key))}</th>`).join("")}${metrics.map(key => `<th>${esc(human(key))}</th>`).join("")}</tr></thead><tbody>${rows.map(row =>
    `<tr><td>${esc(shortOffering(row.label))}</td>${dimensions.map(key => `<td>${esc(key === "offering" ? shortOffering(row.dimensions?.[key]) : row.dimensions?.[key] ?? "—")}</td>`).join("")}${metrics.map(key => `<td>${shown(row.metrics?.[key], 2)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}

function panel(title, subtitle, body, rows = [], wide = false) {
  return `<article class="viz-panel${wide ? " wide" : ""}"><header><div><h3>${esc(title)}</h3>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div></header>${body || '<p class="empty">No data available for this selection.</p>'}${details(rows)}</article>`;
}

function metricCards(items, hero = false) {
  return `<div class="viz-metrics${hero ? " hero" : ""}">${items.map(([label, metric, context]) =>
    `<article class="viz-kpi"><span>${esc(label)}</span><strong>${shown(metric, 2)}</strong>${context ? `<small>${esc(context)}</small>` : ""}</article>`).join("")}</div>`;
}

function bars(rows, metric, labeler = rowLabel, limit = 20, colorer = () => COLORS[0]) {
  const items = rows.map(row => ({ row, value: number(row, metric) })).filter(item => item.value != null).slice(0, limit);
  if (!items.length) return "";
  const max = Math.max(...items.map(item => Math.abs(item.value)), 1);
  return `<div class="hbars">${items.map(({ row, value }) => `<div class="hbar"><span title="${esc(labeler(row))}">${esc(labeler(row))}</span><div><i style="width:${Math.abs(value) / max * 100}%;background:${colorer(row)}"></i></div><b>${value.toLocaleString("en-AU", { maximumFractionDigits: 2 })}</b></div>`).join("")}</div>`;
}

function groupedColumns(rows, metrics, labeler = rowLabel) {
  const values = rows.flatMap(row => metrics.map(key => number(row, key))).filter(value => value != null);
  if (!values.length) return "";
  const max = Math.max(...values, 1);
  return `<div class="column-chart"><div class="column-groups">${rows.map(row => `<div class="column-group"><div class="columns">${metrics.map((key, index) => {
    const value = number(row, key);
    return `<span class="column"><b>${value == null ? "NA" : value.toLocaleString("en-AU", {maximumFractionDigits:2})}</b><i style="height:${value == null ? 0 : Math.max(value / max * 100, value ? 3 : 0)}%;background:${COLORS[index]}" title="${esc(human(key))}: ${value ?? "Not available"}"></i></span>`;
  }).join("")}</div><span>${esc(labeler(row))}</span></div>`).join("")}</div><div class="legend">${metrics.map((key, index) => `<span><i style="background:${COLORS[index]}"></i>${esc(human(key))}</span>`).join("")}</div></div>`;
}

function stacked(items) {
  const legend = new Map();
  const chart = `<div class="stack-list">${items.map(item => {
    const known = item.segments.filter(segment => segment.value != null);
    known.forEach((segment, index) => legend.set(segment.label, segment.color || CATEGORY_COLORS[segment.label] || COLORS[index]));
    const total = known.reduce((sum, segment) => sum + segment.value, 0);
    return `<div class="stack-row"><span title="${esc(item.label)}">${esc(item.label)}</span><div class="stack-track">${known.map((segment, index) => `<i style="width:${total ? segment.value / total * 100 : 0}%;background:${segment.color || COLORS[index]}" title="${esc(segment.label)}: ${segment.value}">${segment.value || ""}</i>`).join("")}</div><b>${total.toLocaleString("en-AU")}</b></div>`;
  }).join("")}</div>`;
  return chart + `<div class="legend">${[...legend].map(([label,color]) => `<span><i style="background:${color}"></i>${esc(human(label))}</span>`).join("")}</div>`;
}

function lineChart(rows, metric, { xKey = "period", seriesKey, seriesLabel, numeric = false, aggregate = false, xTitle = "Reporting period", yTitle = human(metric), yMax } = {}) {
  // Unknown positions stay in the folded data; they cannot have numeric coordinates.
  if (numeric) rows = rows.filter(row => row.dimensions?.[xKey] != null && Number.isFinite(Number(row.dimensions[xKey])));
  let names = [...new Set(rows.map(row => seriesKey ? row.dimensions?.[seriesKey] : "All").filter(Boolean))].slice(0, 7);
  const periods = [...new Set(rows.map(row => row.dimensions?.[xKey]).filter(value => value != null))]
    .sort((a, b) => numeric ? Number(a) - Number(b) : String(a).localeCompare(String(b)));
  if (!periods.length || !names.length) return "";
  const values = new Map();
  rows.forEach(row => {
    const value = number(row, metric), period = row.dimensions?.[xKey], name = seriesKey ? row.dimensions?.[seriesKey] : "All";
    if (value == null || period == null || !name) return;
    const key = `${name}\u0000${period}`;
    values.set(key, aggregate ? (values.get(key) || 0) + value : value);
  });
  if (!values.size) return "";
  names = names.filter(name => periods.some(period => values.has(`${name}\u0000${period}`)));
  const max = yMax || Math.max(...values.values(), 1), width = 860, height = 290, left = 58, right = 25, top = 35, bottom = 65;
  const x = index => left + (numeric ? (Number(periods[index]) - Number(periods[0])) / (Number(periods.at(-1)) - Number(periods[0]) || 1) : index / Math.max(periods.length - 1, 1)) * (width - left - right);
  const y = value => top + (max - value) * (height - top - bottom) / max;
  const paths = names.map((name, index) => {
    const points = periods.map((period, i) => values.has(`${name}\u0000${period}`) ? `${x(i)},${y(values.get(`${name}\u0000${period}`))}` : null);
    const segments = []; let part = [];
    [...points, null].forEach(point => { if (point) part.push(point); else if (part.length) { segments.push(part); part = []; } });
    const dots = periods.map((period, i) => values.has(`${name}\u0000${period}`)
      ? `<circle cx="${x(i)}" cy="${y(values.get(`${name}\u0000${period}`))}" r="3.5" fill="${COLORS[index]}"><title>${esc(seriesLabel ? seriesLabel(name) : human(name))} · ${esc(period)}: ${values.get(`${name}\u0000${period}`)}</title></circle>` : "").join("");
    return segments.filter(segment => segment.length > 1).map(segment => `<polyline points="${segment.join(" ")}" fill="none" stroke="${COLORS[index]}" stroke-width="2"/>`).join("") + dots;
  }).join("");
  const ticks = [...new Set([0, numeric && periods.includes("0") ? periods.indexOf("0") : Math.floor((periods.length - 1) / 2), periods.length - 1])];
  return `<div class="line-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(yTitle)} by ${esc(xTitle)}"><text x="${left}" y="15">${esc(yTitle)}</text><line class="axis" x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}"/><line class="axis" x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}"/><text x="4" y="${top+5}">${max.toLocaleString("en-AU", {maximumFractionDigits:1})}</text><text x="8" y="${y(max/2)+4}">${(max/2).toLocaleString("en-AU", {maximumFractionDigits:1})}</text><text x="25" y="${height-bottom+4}">0</text>${paths}${ticks.map(i => `<text x="${x(i)}" y="${height-bottom+20}" text-anchor="middle">${esc(periods[i])}</text>`).join("")}<text x="${width/2}" y="${height-8}" text-anchor="middle">${esc(xTitle)}</text></svg><div class="legend">${names.map((name, index) => `<span><i style="background:${COLORS[index]}"></i>${esc(seriesLabel ? seriesLabel(name) : seriesKey === "offering" ? shortOffering(name) : human(name))}</span>`).join("")}</div></div>`;
}

function heatmap(rows, rowKey, columnKey, metric, { parseRow, parseColumn, aggregate = false } = {}) {
  const normalized = rows.map(row => ({ row, r: parseRow ? parseRow(row) : row.dimensions?.[rowKey], c: parseColumn ? parseColumn(row) : row.dimensions?.[columnKey], value: number(row, metric) }))
    .filter(item => item.r != null && item.c != null);
  const rowNames = [...new Set(normalized.map(item => item.r))], columns = [...new Set(normalized.map(item => item.c))].sort();
  if (!rowNames.length || !columns.length) return "";
  const values = new Map();
  normalized.forEach(item => { const key = `${item.r}\u0000${item.c}`; if (item.value != null) values.set(key, aggregate ? (values.get(key) || 0) + item.value : item.value); });
  const max = Math.max(...values.values(), 1);
  return `<div class="heatmap-wrap"><table class="heatmap"><thead><tr><th></th>${columns.map(column => `<th>${esc(human(column))}</th>`).join("")}</tr></thead><tbody>${rowNames.map(name => `<tr><th>${esc(rowKey === "offering" ? shortOffering(name) : human(name))}</th>${columns.map(column => {
    const value = values.get(`${name}\u0000${column}`);
    return `<td style="--heat:${value == null ? 0 : Math.max(.08, value / max)}">${value == null ? "—" : value.toLocaleString("en-AU", {maximumFractionDigits:1})}</td>`;
  }).join("")}</tr>`).join("")}</tbody></table></div><div class="heat-legend"><span>Lower</span><i></i><span>Higher</span></div>`;
}

function coverageMatrix(coverage) {
  const entries = Object.entries(coverage || {}), sources = [...new Set(entries.flatMap(([, value]) => Object.keys(value)))];
  if (!entries.length) return "";
  return `<article class="viz-panel wide"><h3>Data coverage</h3><div class="table-wrap"><table class="coverage-table"><thead><tr><th>Offering</th>${sources.map(source => `<th>${esc(human(source))}</th>`).join("")}</tr></thead><tbody>${entries.map(([offering, value]) => `<tr><td title="${esc(offering)}">${esc(shortOffering(offering))}</td>${sources.map(source => `<td class="${value[source] ? "available" : "unavailable"}">${value[source] ? "✓" : "Unavailable"}</td>`).join("")}</tr>`).join("")}</tbody></table></div></article>`;
}

function calendar(rows) {
  if (!rows.length) return "";
  return `<div class="table-wrap"><table><thead><tr><th>Offering</th><th>Course start</th><th>Course end</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(shortOffering(row.dimensions.offering))}</td><td>${esc(row.dimensions.starts_on)}</td><td>${esc(row.dimensions.ends_on)}</td></tr>`).join("")}</tbody></table></div>`;
}

function gauges(rows) {
  return `<div class="gauge-grid">${rows.map((row, index) => {
    const value = number(row, "mean_agreement"), pct = value == null ? 0 : Math.max(0, Math.min(100, value / 5 * 100));
    return `<article><small>${esc(shortOffering(row.dimensions?.offering))}</small><div class="gauge" style="--score:${pct}%;--colour:${COLORS[index % COLORS.length]}"><span>${value == null ? "NA" : value.toFixed(2)}<small>/5</small></span></div><b>${esc(human(row.dimensions?.theme || row.label))}</b><small>${shown(row.metrics?.valid_responses)} valid responses</small></article>`;
  }).join("")}</div>`;
}

function nps(row) {
  if (!row) return "";
  const values = ["detractor_pct", "passive_pct", "promoter_pct"].map(key => number(row, key) || 0);
  return `<div class="nps"><strong>${shown(row.metrics?.nps, 1)}</strong><div><div class="nps-track">${values.map((value,index) => `<i style="width:${value}%;background:${["#c4515c","#dca547","#438a69"][index]}"></i>`).join("")}</div><div class="legend"><span>Detractor ${values[0].toFixed(1)}%</span><span>Passive ${values[1].toFixed(1)}%</span><span>Promoter ${values[2].toFixed(1)}%</span></div><small>${shown(row.metrics?.valid_responses)} valid responses</small></div></div>`;
}

function likert(questions, distribution) {
  if (!questions.length || !distribution.length) return "";
  const chart = `<div class="likert">${questions.map(question => {
    const rows = distribution.filter(row => row.dimensions?.offering === question.dimensions?.offering && row.dimensions?.question === question.dimensions?.question);
    const counts = [1,2,3,4,5].map(score => number(rows.find(row => String(row.dimensions?.agreement) === String(score)), "responses") || 0), total = counts.reduce((a,b) => a+b,0);
    return `<div class="likert-row"><span title="${esc(question.label)}">${esc(question.label)}<small>${esc(shortOffering(question.dimensions?.offering))}</small></span><div>${counts.map((value,index) => `<i style="width:${total ? value/total*100 : 0}%;background:${["#9f3131","#d77973","#898781","#78a9df","#245b99"][index]}" title="${index+1}: ${value} valid responses"></i>`).join("")}</div><b title="Mean agreement out of 5">${shown(question.metrics?.mean_agreement,2)}</b><small>${shown(question.metrics?.valid_responses)} responses</small></div>`;
  }).join("")}</div>`;
  const labels = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"];
  return chart + `<div class="legend likert-legend">${labels.map((label,index) => `<span><i style="background:${["#9f3131","#d77973","#898781","#78a9df","#245b99"][index]}"></i>${index+1} · ${label}</span>`).join("")}</div>`;
}

const GRADE_COLORS = { below_70: "#c4515c", "70_to_below_80": "#d9792b", "80_and_above": "#438a69", unknown: "#8793a5" };
const TIMING_LABELS = {
  early_over_7d: "More than 7 days early", early_1_7d: "1–7 days early", final_24h: "Final 24 hours",
  late_0_1d: "Up to 1 day late", late_1_7d: "1–7 days late", late_over_7d: "More than 7 days late",
  no_observed_submission: "No observed submission"
};
const TIMING_COLORS = Object.fromEntries(Object.keys(TIMING_LABELS).map(key => [key,
  key.startsWith("late_") ? "#c4515c" : key === "no_observed_submission" ? "#8793a5" : "#438a69"]));
const percent = (part, total) => part == null || total == null || !total ? "Not available" : `${(part / total * 100).toFixed(1)}%`;

function weightedSummary(rows) {
  return `<div class="result-summaries">${rows.map(row => {
    const observed=number(row,"observed_memberships"), complete=number(row,"complete_grades"), unknown=number(row,"unknown"), passed=number(row,"passed");
    const rule=row.dimensions.calculation_rule || "Rule not provided", threshold=row.dimensions.pass_threshold_pct;
    return `<article><h4>${esc(shortOffering(row.dimensions.offering))}</h4><p class="rule-note">${esc(rule)}${threshold == null ? "" : ` · Pass threshold ≥ ${esc(Number(threshold))}%`}</p><dl>
      <dt>Grade coverage</dt><dd>${complete ?? "NA"} / ${observed ?? "NA"} (${percent(complete,observed)})</dd>
      <dt>Unknown grades</dt><dd>${unknown ?? "NA"} (${percent(unknown,observed)})</dd>
      <dt>Passed among complete</dt><dd>${passed ?? "NA"} / ${complete ?? "NA"} (${percent(passed,complete)})</dd>
      <dt>Mean among complete</dt><dd>${shown(row.metrics.mean_weighted_pct,1,"%")}</dd>
    </dl><small>Whole offering; selecting one assignment does not change this denominator. Academic pass is independent of Badge.</small></article>`;
  }).join("")}</div>`;
}

function gradeDistribution(rows) {
  return `<div class="mini-grid">${Object.entries(byOffering(rows)).map(([offering,group]) => `<section class="mini-viz"><h4>${esc(shortOffering(offering))}</h4>${bars(group,"memberships",row=>human(row.dimensions.band),Infinity,row=>GRADE_COLORS[row.dimensions.band])}</section>`).join("")}</div>`;
}

function academic(tables) {
  const rows=tables.academic_results || [], distribution=tables.weighted_grade_distribution || [];
  return panel("Weighted outcomes", "Coverage is shown before the pass rate; unavailable grades are not zero.",weightedSummary(rows),rows,true) +
    panel("Weighted grade distribution","Below 70 is red; unknown grades are grey.",gradeDistribution(distribution),distribution,true);
}

function notes(data) {
  return data.notes?.length ? `<details class="viz-panel wide notes"><summary>Definitions and limitations (${data.notes.length})</summary><ul>${data.notes.map(note => `<li>${esc(note)}</li>`).join("")}</ul></details>` : "";
}

function renderOverview(data, ctx) {
  const m = data.metrics, t = data.tables;
  ctx.metrics.innerHTML = metricCards([
    ["Offerings in scope",m.offerings,"Selected course"],["Assignment students",m.assignment_students,"Distinct source students"],
    ["Engagement students",m.engagement_students,"Distinct source students"],["Matched in both",m.intersection_students,"Source intersection"],
    ["Survey responses",m.survey_completed_responses,"Completed responses"],["Support cases",m.support_records,"Case records"]
  ]);
  ctx.coverage.innerHTML = coverageMatrix(data.coverage);
  const feedback = `${gauges(t.survey_themes || [])}${nps((t.survey_nps || [])[0])}${details(t.survey_questions || [],"Survey question detail")}`;
  const supportRows = t.support_channels || [];
  ctx.tables.innerHTML = [
    panel("Offering comparison","Assignment and Engagement students use separate source cohorts",groupedColumns(t.offering_comparison || [],["assignment_students","engagement_students"]),t.offering_comparison || [],true),
    panel("Course dates","Confirmed start and end dates for each teaching period.",calendar(t.course_calendar || []),[],true),
    academic(t),
    panel("Learner feedback","Theme agreement uses completed questionnaires with at least half the theme items answered; recommendation uses its own valid-response count",feedback,[...(t.survey_themes||[]),...(t.survey_nps||[])],true),
    panel("Support operations","Channel share and response time",`${metricCards([["Case records",(t.support_summary||[])[0]?.metrics?.records],["Median response hours",(t.support_summary||[])[0]?.metrics?.median_response_hours]])}${bars(supportRows,"records",row=>human(row.dimensions?.group||row.label))}`,supportRows,true)
  ].join("");
  ctx.notes.innerHTML = notes(data);
}

function issueList(rows, selected) {
  const filtered = selected === "all" ? rows : rows.filter(row => row.dimensions?.topic === selected), max = Math.max(...filtered.map(row => number(row,"records")||0),1);
  return `<div class="issue-list">${filtered.map(row => { const value=number(row,"records"); return `<article><div><span>${esc(human(row.dimensions?.topic))}</span><b>${value ?? "NA"}</b></div><p>${esc(row.label)}</p><i style="width:${value == null ? 0 : value/max*100}%"></i></article>`; }).join("")}</div>`;
}

function renderEngagement(data, ctx) {
  const t=data.tables, m=data.metrics;
  ctx.metrics.innerHTML=metricCards([["Students",m.students],["Views",m.views],["Participations",m.participations],["Views per student",m.views_per_student],["Support records",m.support_records]]);
  ctx.coverage.innerHTML="";
  const activity=t.activity_by_start_date||[];

  const activityCharts=["views","students","participations"].map(key=>`<section class="mini-viz"><h4>${human(key)}</h4>${lineChart(activity,key,{seriesKey:"category"})}</section>`).join("");
  const issues=t.support_issue_summaries||[], topics=[...new Set(issues.map(row=>row.dimensions?.topic).filter(Boolean))], selected=topics.includes(ctx.state.supportTopic)?ctx.state.supportTopic:"all";
  const issueButtons=`<div class="chips" id="issueTopics"><button data-topic="all" class="${selected==="all"?"active":""}">All topics</button>${topics.map(topic=>`<button data-topic="${esc(topic)}" class="${selected===topic?"active":""}">${esc(human(topic))}</button>`).join("")}</div><div id="issueList">${issueList(issues,selected)}</div>`;
  ctx.tables.innerHTML=[
    panel("Resource categories","Students overlap across categories",["students","views","participations"].map(key=>`<section class="mini-viz"><h4>${human(key)}</h4>${bars(t.resource_categories||[],key,row=>human(row.dimensions?.category))}</section>`).join(""),t.resource_categories||[],true),
    panel("Activity by first-view date","Each resource summary’s full count is attributed to its first-view date; this is not a daily click log.",`<div class="mini-grid">${activityCharts}</div>`,activity,true),
    panel("Activity by course week","Views by offering, summed across resource categories",lineChart(t.activity_by_course_week||[],"views",{seriesKey:"offering",numeric:true,aggregate:true,xTitle:"Week relative to course start"}),t.activity_by_course_week||[],true),
    panel("Activity by course phase","Views by offering and learning phase",heatmap(t.activity_by_course_phase||[],"offering","period","views",{aggregate:true}),t.activity_by_course_phase||[],true),
    panel("Support summary","Case records and confirmed response hours",metricCards([["Records",(t.support_summary||[])[0]?.metrics?.records],["Responses measured",(t.support_summary||[])[0]?.metrics?.response_n],["Median response hours",(t.support_summary||[])[0]?.metrics?.median_response_hours]]),t.support_summary||[]),
    panel("Support status","Open, closed and unknown records",bars(t.support_status||[],"records",row=>human(row.dimensions?.group)),t.support_status||[]),
    panel("Support records over time","Counts and response time use separate scales",`<div class="mini-grid"><section class="mini-viz"><h4>Case records</h4>${lineChart(t.support_timeline||[],"records",{xKey:"group"})}</section><section class="mini-viz"><h4>Median response hours</h4>${lineChart(t.support_timeline||[],"median_response_hours",{xKey:"group"})}</section></div>`,t.support_timeline||[],true),
    panel("Support channels","Records by contact channel",bars(t.support_channels||[],"records",row=>human(row.dimensions?.group)),t.support_channels||[]),
    panel("Response-time distribution","Age (Hours) is confirmed response time",bars(t.support_response_distribution||[],"records",row=>human(row.dimensions?.group)),t.support_response_distribution||[]),
    panel("Support topics","Keyword topics can overlap",bars(t.support_topics||[],"records",row=>human(row.dimensions?.group)),t.support_topics||[]),
    panel("Support topics over time","Darker cells represent more matched case records",heatmap(t.support_topics_timeline||[],"course","group","records",{parseRow:row=>String(row.dimensions?.group||"").split(":").slice(1).join(":"),parseColumn:row=>String(row.dimensions?.group||"").split(":")[0]}),t.support_topics_timeline||[],true),
    panel("Support records by weekday","Monday is 0 and Sunday is 6",bars([...(t.support_weekdays||[])].sort((a,b)=>Number(a.dimensions?.group)-Number(b.dimensions?.group)),"records",row=>["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][Number(row.dimensions?.group)]||row.label),t.support_weekdays||[]),
    panel("Representative support issues","Frequent redacted issue subjects grouped by topic",issueButtons,issues,true)
  ].join("");
  ctx.notes.innerHTML=notes(data);
  document.querySelectorAll("#issueTopics button").forEach(button=>button.onclick=()=>{ctx.state.supportTopic=button.dataset.topic;renderEngagement(data,ctx);});
}

function byOffering(rows) {
  return Object.groupBy ? Object.groupBy(rows,row=>row.dimensions?.offering||"Unknown") : rows.reduce((out,row)=>{const key=row.dimensions?.offering||"Unknown";(out[key]||=[]).push(row);return out;},{});
}
function assignmentName(row) {
  const key=row.dimensions?.assessment_key;
  return key && key!=="unconfirmed" ? key : row.dimensions?.assignment_name || row.label;
}

// Group bands beneath their assignment name, rather than repeating raw API labels.
function assignmentDistribution(rows, name, labels={}, colors={}) {
  const groups=rows.reduce((all,row)=>{(all[row.dimensions.assignment_ref]||=[]).push(row);return all;},{});
  return `<div class="mini-grid">${Object.entries(groups).map(([ref,group])=>{
    const order=Object.keys(labels);
    group.sort((a,b)=>order.length ? order.indexOf(a.dimensions.band)-order.indexOf(b.dimensions.band) : String(a.dimensions.band).localeCompare(String(b.dimensions.band)));
    return `<section class="mini-viz"><h4>${esc(name(ref))}</h4>${bars(group,"students",row=>labels[row.dimensions.band]||human(row.dimensions.band),Infinity,row=>colors[row.dimensions.band]||COLORS[0])}</section>`;
  }).join("")}</div>`;
}

function deadlineBadges(rows) {
  const active=rows.filter(row=>number(row,"students")>0);
  const labels={due:"Deadline passed",not_yet_due:"Not yet due",unknown_deadline:"Deadline not provided"};
  return `<div class="deadline-badges">${active.length ? active.map(row=>`<span class="deadline-${esc(row.dimensions.status)}">${esc(labels[row.dimensions.status])} · ${number(row,"students")} students</span>`).join("") : "<span>Deadline status unavailable</span>"}</div>`;
}

function timingSummary(rows, name) {
  return `<div class="result-summaries">${rows.map(row=>{
    const days=number(row,"median_days_relative_to_deadline");
    const timing=days==null ? "Not available" : days===0 ? "At the deadline" : `${Math.abs(days).toFixed(1)} days ${days<0?"before":"after"} deadline`;
    return `<article><h4>${esc(name(row.dimensions.assignment_ref))}</h4><dl>
      <dt>Submitted in final 24 hours</dt><dd>${shown(row.metrics.final_24h_pct_among_submitted,1,"%")}</dd>
      <dt>Median submission</dt><dd>${timing}</dd>
      <dt>Median grading interval</dt><dd>${shown(row.metrics.median_grading_days,1," days after submission")}</dd>
    </dl><small>Final 24h uses observed submissions after the deadline has passed. Grading interval uses ${shown(row.metrics.grading_interval_n,0)} valid submission-to-grading timestamps, not feedback release.</small></article>`;
  }).join("")}</div>`;
}

function renderAssignments(data,ctx) {
  const t=data.tables,m=data.metrics,assessments=t.assessments||[],groups=byOffering(assessments),sections=[];
  ctx.metrics.innerHTML=metricCards([["Assignment students",m.students,"Distinct students across the selected assignments"]]);
  ctx.coverage.innerHTML="";
  sections.push(`<section class="page-section"><header><h3>Assignment overview</h3><p>Each assignment has its own submission and grade denominator. Deadline status reflects the reporting date; an absent deadline is not assumed to mean no deadline.</p></header><div class="assignment-cards">${assessments.map(row=>{
    const deadline=(t.assignment_deadline_coverage||[]).filter(item=>item.dimensions.offering===row.dimensions.offering&&item.dimensions.assignment_ref===row.dimensions.assignment_ref);
    const name=assignmentName(row),fullName=row.label===name?"":`<p class="assignment-title">${esc(row.label)}</p>`;
    const score = row.dimensions.kind === "self_assessment" ? '<small>Non-scored activity</small>' : `<b>${shown(row.metrics.mean_score_pct,1,"%")}</b><small>mean valid score</small>`;
    return `<article><span>${esc(shortOffering(row.dimensions.offering))}</span><h4>${esc(name)}</h4>${fullName}${deadlineBadges(deadline)}<div class="assignment-kpis"><div><b>${shown(row.metrics.students,0)}</b><small>observed students</small></div><div><b>${shown(row.metrics.submission_rate_pct,1,"%")}</b><small>submitted</small></div><div>${score}</div></div></article>`;
  }).join("")}</div>${details(assessments)}${details(t.assignment_deadline_coverage||[],"Deadline status data")}</section>`);
  for (const [offering,rows] of Object.entries(groups)) {
    const refs=new Set(rows.map(row=>row.dimensions.assignment_ref));
    const select=key=>(t[key]||[]).filter(row=>row.dimensions.offering===offering&&refs.has(row.dimensions.assignment_ref));
    const name=ref=>assignmentName(rows.find(row=>row.dimensions.assignment_ref===ref)||{label:"Unmapped assignment",dimensions:{}});
    const hasScored=rows.some(row=>row.dimensions.kind==="scored")&&ctx.state.mode!=="self_assessment";
    const scoredRefs=new Set(rows.filter(row=>row.dimensions.kind==="scored").map(row=>row.dimensions.assignment_ref));
    const scoreRows=select("score_distribution").filter(row=>scoredRefs.has(row.dimensions.assignment_ref));
    const dueRefs=new Set(select("assignment_deadline_coverage").filter(row=>row.dimensions.status==="due"&&number(row,"students")>0).map(row=>row.dimensions.assignment_ref));
    const dueRows=key=>select(key).filter(row=>dueRefs.has(row.dimensions.assignment_ref));
    const statusItems=rows.map(item=>({label:assignmentName(item),segments:select("submission_status").filter(row=>row.dimensions.assignment_ref===item.dimensions.assignment_ref).map(row=>({label:row.dimensions.band,value:number(row,"students"),color:CATEGORY_COLORS[row.dimensions.band]}))}));
    const academicRows=(t.academic_results||[]).filter(row=>row.dimensions.offering===offering);
    const weightedRows=(t.weighted_grade_distribution||[]).filter(row=>row.dimensions.offering===offering);
    sections.push(`<section class="page-section"><header><h3>${esc(shortOffering(offering))}</h3><p>Assignment activity for this teaching period.</p></header><div class="viz-grid">
      ${panel("Completion and submission status","Submitted and graded are source states. Missing flags remain independent and are available in the folded data.",stacked(statusItems)+details(select("missing_flag"),"Source missing flags"),select("submission_status"),true)}
      ${panel("Late submission flag","Not marked late does not establish on-time submission; it can include unsubmitted records.",assignmentDistribution(select("late_flag"),name,{no:"Not marked late",yes:"Marked late",unknown:"Unknown"},{yes:"#c4515c",no:"#438a69",unknown:"#8793a5"}),select("late_flag"),true)}
      ${panel("Attempt distribution","Latest exported attempt number; missing attempt counts remain unknown.",assignmentDistribution(select("attempt_distribution"),name,{"1":"One attempt","2":"Two attempts","3_plus":"More than two attempts",unknown:"Attempt count unknown"}),select("attempt_distribution"),true)}
      ${dueRefs.size?panel("Cumulative submission","Y: submitted students / all students whose deadline has passed (%). X: days relative to the deadline; 0 is the deadline. Future follow-up stays unavailable.",lineChart(dueRows("assignment_cumulative_submission"),"submitted_pct",{xKey:"days_relative_to_deadline",seriesKey:"assignment_ref",seriesLabel:name,numeric:true,xTitle:"Days relative to deadline (0 = deadline)",yTitle:"Cumulative submitted (%)",yMax:100})||'<p class="empty">No eligible deadline has passed, or no fully observed follow-up is available.</p>',dueRows("assignment_cumulative_submission"),true):""}
      ${dueRefs.size?panel("Submission timing","Counts within time bands: green is at/before the deadline, red is after it, grey is no observed submission. Only students whose deadline has passed are included.",dueRows("assignment_submission_timing").length?assignmentDistribution(dueRows("assignment_submission_timing"),name,TIMING_LABELS,TIMING_COLORS):'<p class="empty">No eligible deadline has passed, or deadline information is unavailable.</p>',dueRows("assignment_submission_timing"),true):""}
      ${dueRefs.size?panel("Deadline and grading summary","Percentages and time intervals are shown separately for each assignment. Relative days use source deadlines, which can differ from course end.",timingSummary(dueRows("assignment_time_summary"),name),dueRows("assignment_time_summary"),true):""}
      ${hasScored?panel("Assignment score distribution","Scored assignments only. Valid grades use percentage bands; unknown includes records without a valid score.",assignmentDistribution(scoreRows,name,{below_70:"Below 70", "70_to_below_80":"70–<80", "80_and_above":"80 and above",unknown:"No valid score"},GRADE_COLORS),scoreRows,true):""}
      ${hasScored?panel("Weighted grade distribution","Whole offering; red is below 70, grey is unknown.",gradeDistribution(weightedRows),weightedRows,true):""}
      ${hasScored?panel("Weighted outcomes","Coverage is shown before the pass rate; incomplete grades never become zero.",weightedSummary(academicRows),academicRows,true):""}
      ${select("self_assessment_completion").length?panel("Self-assessment activity","Completion means submitted/graded participation, not a score.",assignmentDistribution(select("self_assessment_completion"),name),select("self_assessment_completion"),true):""}
    </div></section>`);
  }
  if ((t.assignment_pair_submission||[]).length) {
    const pair=t.assignment_pair_submission[0].dimensions, left=assessments.find(row=>row.dimensions.assignment_ref===pair.first_assignment),right=assessments.find(row=>row.dimensions.assignment_ref===pair.second_assignment);
    const names={both_submitted:"Both submitted",first_only:`${assignmentName(left||{label:"First assignment"})} only`,second_only:`${assignmentName(right||{label:"Second assignment"})} only`,neither_submitted:"Neither submitted"};
    sections.push(panel("Selected assignment pair","Only records present for both selected assignments with both deadlines passed.",bars(t.assignment_pair_submission,"students",row=>names[row.key]),t.assignment_pair_submission,true));
  }
  ctx.tables.innerHTML=sections.join("");ctx.notes.innerHTML=notes(data);
}

function comments(rows){
  const groups=byOffering(rows.map(row=>({...row,dimensions:{...row.dimensions,offering:row.dimensions?.question_group||"Other"}})));
  return `<div class="comment-groups">${Object.entries(groups).map(([group,items],index)=>`<details ${index===0?"open":""}><summary>${esc(human(group))} <span>${items.length} comments</span></summary>${items.map(row=>`<article><p>${esc(row.label)}</p><span>${shown(row.metrics?.responses)} response${number(row,"responses")===1?"":"s"}</span></article>`).join("")}</details>`).join("")}</div>`;
}

function renderOutcomes(data,ctx){
  const t=data.tables,m=data.metrics, tab=ctx.state.outcomesTab||"badge";
  ctx.metrics.innerHTML=metricCards([["Badge completion rate",m.badge_completion_rate_pct,"Percent"],["Cohort memberships",m.cohort_memberships],["Valid Badge holders",m.valid_award_holders],["Revoked-only holders",m.revoked_only_holders],["Survey responses",m.survey_completed_responses]],true);
  ctx.coverage.innerHTML="";
  const badgeItems=[{label:"Selected cohort",segments:(t.badge_status||[]).map(row=>({label:row.key,value:number(row,"memberships"),color:CATEGORY_COLORS[row.key]}))}];
  const panels={
    badge:[panel("Badge status of the cohort","Valid, revoked-only, review and unmatched states",stacked(badgeItems),t.badge_status||[],true),panel("Badge outcomes by offering","Cohort size and valid Badge holders",groupedColumns(t.offering_comparison||[],["cohort_students","valid_award_holders"]),t.offering_comparison||[],true),panel("Badge completion rate","Valid matched non-revoked holders divided by Engagement cohort",bars(t.offering_comparison||[],"badge_completion_rate_pct"),t.offering_comparison||[]),panel("Award timeline","Badge memberships by status",lineChart(t.award_timeline||[],"memberships",{seriesKey:"status"}),t.award_timeline||[],true),panel("Delay from course end","Badge holders by delay band",bars(t.badge_delay_from_course_end||[],"holders",row=>`${shortOffering(row.dimensions?.offering)} · ${human(row.dimensions?.band)}`),t.badge_delay_from_course_end||[],true)].join(""),
    academic:academic(t),
    survey:[panel("Would they recommend it?","NPS composition",nps((t.survey_nps||[])[0]),t.survey_nps||[]),panel("Survey theme scores","Agreement responses use 1–5. Valid responses count completed questionnaires with at least half of that theme’s items answered; each questionnaire is weighted equally.",gauges(t.survey_themes||[]),t.survey_themes||[],true),panel("Question response distribution","Each item uses its own valid-answer count. Counts can differ because questions were skipped; theme and item counts are not the same denominator.",likert(t.survey_questions||[],t.survey_distribution||[]),[...(t.survey_questions||[]),...(t.survey_distribution||[])],true),panel("Feedback topics","Keyword categories can overlap",bars(t.survey_feedback_topics||[],"responses",row=>`${human(row.dimensions?.question_group)} · ${human(row.label)}`),t.survey_feedback_topics||[],true),panel("Anonymous feedback comments","Direct identifiers are removed before display",comments(t.survey_feedback_comments||[]),t.survey_feedback_comments||[],true)].join(""),
    diagnostics:[panel("Award diagnostics","Reasons records could or could not be matched",bars(t.award_diagnostics||[],"records",row=>human(row.label)),t.award_diagnostics||[],true),panel("Source snapshots","Latest completed source snapshots",`<div class="snapshot-list">${Object.entries(data.snapshots||{}).map(([key,value])=>`<div><span>${esc(human(key))}</span><b>${esc(value)}</b></div>`).join("")}</div>`,[],true),notes(data)].join("")
  };
  const offering=data.filters?.offering, scope=offering ? `Showing offering ${shortOffering(offering)}.` : "Showing all offerings combined; use the Offering selector to view one teaching period.";
  ctx.tables.innerHTML=`<div class="scope-note"><b>Badge analysis scope</b><span>${esc(scope)}</span></div><div class="outcome-tabs" id="outcomeTabs">${[["badge","Badge"],["academic","Academic results"],["survey","Survey"],["diagnostics","Diagnostics"]].map(([key,label])=>`<button data-tab="${key}" class="${tab===key?"active":""}">${label}</button>`).join("")}</div><div class="viz-grid">${panels[tab]}</div>`;
  ctx.notes.innerHTML="";
  document.querySelectorAll("#outcomeTabs button").forEach(button=>button.onclick=()=>{ctx.state.outcomesTab=button.dataset.tab;renderOutcomes(data,ctx);});
}

export function renderSpecialPage(data,{state,el}){
  const renderer={overview:renderOverview,engagement:renderEngagement,assignments:renderAssignments,outcomes:renderOutcomes}[data.page];
  if(!renderer)return false;
  const ctx={state,metrics:el("metrics"),coverage:el("coverage"),tables:el("tables"),notes:el("notes")};
  [ctx.metrics,ctx.coverage,ctx.tables,ctx.notes].forEach(node=>node.classList.add("special-page"));
  renderer(data,ctx);return true;
}

export function clearSpecialPage(el){["metrics","coverage","tables","notes"].forEach(id=>el(id).classList.remove("special-page"));}
