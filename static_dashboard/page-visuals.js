"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5", "#c4515c", "#4b8795", "#768399"];
const BAND_LABELS = {
  below_70: "Below 70", "70_to_below_80": "70–<80", "80_and_above": "80 and above",
  unknown: "Unknown", yes: "Yes", no: "No", submitted: "Submitted", unsubmitted: "Unsubmitted",
  graded: "Graded", excused: "Excused", not_late: "Not late", no_observed_submission: "No submission",
  content: "Content", assessment: "Assessment", other: "Other Canvas areas",
  discussions: "Discussions", user_profiles: "User/profile pages", announcements: "Announcements",
  calendar_events: "Calendar events", external_tools: "External tools", grades: "Grades",
  passed: "Passed", below_pass_mark: "Fail", result_unavailable: "Result unavailable",
  passed_and_badge: "Passed and Badge recorded", passed_no_badge_record: "Passed, no Badge record",
  badge_recorded_pass_not_confirmed: "Badge recorded, pass not confirmed", neither_confirmed: "Neither confirmed",
  valid: "Active Badge recorded", revoked_only: "Revoked Badge only",
  needs_review: "Teaching period could not be confirmed", no_matched_award: "No Badge record found",
  cohort_students: "Students represented", confirmed_course_passes: "Confirmed course passes",
  valid_award_holders: "Students with an active Badge", assignment_students: "Total number of students",
  engagement_students: "Students with Canvas activity", revoked: "Revoked Badge",
  students: "Students (count)", views: "Page views (count)", responses: "Responses (count)",
  records: "Cases (count)", submitted_students: "Students submitted (count)",
  total_students: "Total students (count)", submitted_pct: "Submitted (%)",
  valid_responses: "Valid responses (count)", mean_agreement: "Mean agreement (1–5)",
  median_response_hours: "Median response time (hours)",
  response_n: "Cases with response time (count)",
  memberships: "Students (count)", holders: "Students (count)",
  award_records: "Badge records (count)", cohort_students: "Total students (count)",
  confirmed_course_passes: "Confirmed passes (count)",
  confirmed_passes: "Confirmed passes (count)", active_badges: "Active Badges (count)",
  passed_students: "Passed students (count)", below_pass_mark_students: "Failed students (count)",
  result_unavailable_students: "Results unavailable (count)",
  submission_rate_pct: "Submitted (%)", pass_rate_pct: "Passed among valid results (%)",
  mean_score_pct: "Mean score (%)", mean_weighted_pct: "Mean weighted result (%)",
  pass_rate_among_complete_pct: "Passed among complete results (%)",
  created_date: "Release proxy date", deadline_date: "Assignment deadline",
  days_from_creation: "Days since assignment creation",
  before_course_start: "Before course start", week_1: "Week 1", week_2: "Week 2",
  weeks_3_4: "Weeks 3–4", week_5_or_later: "Week 5 or later"
};
const CATEGORY_COLORS = {
  submitted: "#438a69", graded: "#2878b5", unsubmitted: "#8793a5", missing: "#c4515c",
  excused: "#8057a5", valid: "#438a69", passed: "#438a69", below_pass_mark: "#c4515c",
  result_unavailable: "#8793a5", revoked_only: "#c4515c",
  passed_and_badge: "#438a69", passed_no_badge_record: "#d9792b",
  badge_recorded_pass_not_confirmed: "#8057a5", neither_confirmed: "#8793a5",
  needs_review: "#d9792b", no_matched_award: "#8793a5", unknown: "#768399"
};
const LIKERT_COLORS = ["#9f3131", "#d77973", "#898781", "#78a9df", "#245b99"];
const LIKERT_LABELS = ["Strongly disagree", "Slightly disagree", "Neither agree nor disagree", "Slightly agree", "Strongly agree"];
const QUESTION_GROUP_ORDER = ["course_experience", "learning_experience", "impact", "assessment"];
const QUESTION_GROUPS = {
  course_experience: ["Q1", "To what extent do you agree or disagree with the following statements made about the Melbourne MicroCert?"],
  learning_experience: ["Q3", "Thinking about your learning experience, to what extent do you agree or disagree with the following statements about the Melbourne MicroCert?"],
  impact: ["Q4", "Thinking about the impact of your learning, to what extent do you agree or disagree with the following statements about the Melbourne MicroCert?"],
  assessment: ["Q5", "To what extent do you agree or disagree with the following statements about Melbourne MicroCert assessment tasks?"]
};
const FEEDBACK_GROUPS = {
  recommendation_reason: "Reason for recommendation rating",
  application: "Workplace application",
  best_aspects: "Best aspects",
  improvements: "Suggested improvements"
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
    `<tr><td>${esc(shortOffering(row.label))}</td>${dimensions.map(key => `<td>${esc(key === "offering" ? shortOffering(row.dimensions?.[key]) : row.dimensions?.[key] ?? "—")}</td>`).join("")}${metrics.map(key => `<td>${shown(row.metrics?.[key], 2, key.endsWith("_pct") || key === "nps" ? "%" : "")}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
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

function lineChart(rows, metric, { xKey = "period", seriesKey, seriesLabel, numeric = false, aggregate = false, xTitle = "Reporting period", yTitle = human(metric), yMax, markers = [] } = {}) {
  // Unknown positions stay in the folded data; they cannot have numeric coordinates.
  if (numeric) rows = rows.filter(row => row.dimensions?.[xKey] != null && Number.isFinite(Number(row.dimensions[xKey])));
  let names = [...new Set(rows.map(row => seriesKey ? row.dimensions?.[seriesKey] : "All").filter(Boolean))].slice(0, 7);
  const periods = [...new Set([...rows.map(row => row.dimensions?.[xKey]), ...markers.map(marker => marker.period)].filter(value => value != null))]
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
  const markerSvg = markers.map((marker, index) => {
    const position = periods.indexOf(marker.period);
    if (position < 0) return "";
    return `<line x1="${x(position)}" y1="${top}" x2="${x(position)}" y2="${height-bottom}" class="deadline-marker"><title>${esc(marker.label)} · ${esc(marker.date || marker.period)}</title></line><text x="${x(position)+4}" y="${top+12+(index%2)*13}" class="deadline-label">${esc(marker.label)}</text>`;
  }).join("");
  const ticks = [...new Set([0, numeric && periods.includes("0") ? periods.indexOf("0") : Math.floor((periods.length - 1) / 2), periods.length - 1])];
  return `<div class="line-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(yTitle)} by ${esc(xTitle)}"><text x="${left}" y="15">${esc(yTitle)}</text><line class="axis" x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}"/><line class="axis" x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}"/><text x="4" y="${top+5}">${max.toLocaleString("en-AU", {maximumFractionDigits:1})}</text><text x="8" y="${y(max/2)+4}">${(max/2).toLocaleString("en-AU", {maximumFractionDigits:1})}</text><text x="25" y="${height-bottom+4}">0</text>${markerSvg}${paths}${ticks.map(i => `<text x="${x(i)}" y="${height-bottom+20}" text-anchor="middle">${esc(periods[i])}</text>`).join("")}<text x="${width/2}" y="${height-8}" text-anchor="middle">${esc(xTitle)}</text></svg><div class="legend">${names.map((name, index) => `<span><i style="background:${COLORS[index]}"></i>${esc(seriesLabel ? seriesLabel(name) : seriesKey === "offering" ? shortOffering(name) : human(name))}</span>`).join("")}${markers.length ? '<span><i class="deadline-key"></i>Assignment deadline</span>' : ""}</div></div>`;
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
  return `<article class="viz-panel wide"><h3>Data availability</h3><p>Shows which verified data sources are available for each teaching period.</p><div class="table-wrap"><table class="coverage-table"><thead><tr><th>Teaching period</th>${sources.map(source => `<th>${esc(human(source))}</th>`).join("")}</tr></thead><tbody>${entries.map(([offering, value]) => `<tr><td title="${esc(offering)}">${esc(shortOffering(offering))}</td>${sources.map(source => `<td class="${value[source] ? "available" : "unavailable"}">${value[source] ? "✓" : "Unavailable"}</td>`).join("")}</tr>`).join("")}</tbody></table></div></article>`;
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
  const score=number(row,"nps"), scoreText=score==null?"Not available":`${score>0?"+":""}${score.toFixed(1)}%`;
  const colours = ["#c4515c", "#dca547", "#438a69"], labels = ["Detractors", "Passives", "Promoters"];
  return `<div class="nps"><div class="nps-score"><small>Net Promoter Score (NPS)</small><strong>${scoreText}</strong><span>Range −100 to +100</span></div><div><div class="nps-track">${values.map((value,index) => `<i style="width:${value}%;background:${colours[index]}" title="${labels[index]}: ${value.toFixed(1)}%"></i>`).join("")}</div><div class="nps-breakdown">${labels.map((label,index)=>`<article style="--segment:${colours[index]}"><i></i><span>${label}</span><strong>${values[index].toFixed(1)}%</strong></article>`).join("")}</div><small>${shown(row.metrics?.valid_responses)} valid responses</small></div></div>`;
}

function likert(questions, distribution) {
  if (!questions.length || !distribution.length) return "";
  const groups = QUESTION_GROUP_ORDER.map(theme => ({ theme, questions: questions.filter(row => row.dimensions?.theme === theme) }))
    .filter(group => group.questions.length);
  return `<div class="survey-questions">${groups.map((group, groupIndex) => {
    const fallback = QUESTION_GROUPS[group.theme] || [human(group.theme), human(group.theme)];
    const groupCode = group.questions[0].dimensions?.question_group || fallback[0];
    const groupLabel = group.questions[0].dimensions?.question_group_label || fallback[1];
    const itemCount = new Set(group.questions.map(row => row.dimensions?.question)).size;
    const rows = [...group.questions].sort((a,b) => String(a.dimensions?.question).localeCompare(String(b.dimensions?.question), undefined, {numeric:true})).map(question => {
      const bins = distribution.filter(row => row.dimensions?.offering === question.dimensions?.offering && row.dimensions?.question === question.dimensions?.question);
      const counts = [1,2,3,4,5].map(score => number(bins.find(row => String(row.dimensions?.agreement) === String(score)), "responses") || 0);
      const total = counts.reduce((sum,value) => sum + value, 0);
      return `<div class="likert-row"><span><b>${esc(question.dimensions?.question)}</b> ${esc(question.label)}<small>${esc(shortOffering(question.dimensions?.offering))}</small></span><div>${counts.map((value,index) => `<i style="width:${total ? value/total*100 : 0}%;background:${LIKERT_COLORS[index]}" title="${LIKERT_LABELS[index]}: ${value} valid responses">${value || ""}</i>`).join("")}</div><b title="Mean agreement out of 5">${shown(question.metrics?.mean_agreement,2)} / 5</b><small>${shown(question.metrics?.valid_responses)} responses</small></div>`;
    }).join("");
    const legend = `<div class="legend likert-legend">${LIKERT_LABELS.map((label,index) => `<span><i style="background:${LIKERT_COLORS[index]}"></i>${index+1} · ${label}</span>`).join("")}</div>`;
    return `<details class="survey-question-group" ${groupIndex===0?"open":""}><summary><span><b>${esc(groupCode)}</b> ${esc(groupLabel)}</span><small>${itemCount} statements</small></summary><div class="survey-question-list">${rows}${legend}</div></details>`;
  }).join("")}</div>`;
}

const percent = (part, total) => part == null || total == null || !total ? "Not available" : `${(part / total * 100).toFixed(1)}%`;

function academic(tables) {
  const rows=tables.academic_results || [];
  const items=rows.map(row=>({label:shortOffering(row.dimensions.offering),segments:[
    {label:"passed",value:number(row,"passed"),color:CATEGORY_COLORS.passed},
    {label:"below_pass_mark",value:number(row,"below_threshold"),color:CATEGORY_COLORS.below_pass_mark},
    {label:"result_unavailable",value:number(row,"unknown"),color:CATEGORY_COLORS.result_unavailable}
  ]}));
  const summaries=`<div class="result-summaries">${rows.map(row=>{
    const complete=number(row,"complete_grades"),passed=number(row,"passed"),unknown=number(row,"unknown"),below=number(row,"below_threshold");
    const threshold=Number(row.dimensions.pass_threshold_pct);
    return `<article><h4>${esc(shortOffering(row.dimensions.offering))}</h4><p class="rule-note">${esc(row.dimensions.calculation_rule||"Pass rule unavailable")} · Pass mark ${Number.isFinite(threshold)?threshold.toLocaleString("en-AU",{maximumFractionDigits:2}):"—"}%</p><dl>
      <dt>Passed among valid results</dt><dd>${passed??"NA"} / ${complete??"NA"} (${percent(passed,complete)})</dd>
      <dt>Fail</dt><dd>${below??"NA"}</dd>
      <dt>Result unavailable</dt><dd>${unknown??"NA"}</dd>
    </dl></article>`;}).join("")}</div>`;
  return panel("Confirmed course pass", "Uses the confirmed AT1/AT2 weighting and pass mark shown for each teaching period. Unavailable results are not treated as failures.", summaries+stacked(items), rows, true);
}

function notes(data) {
  return data.notes?.length ? `<details class="viz-panel wide notes"><summary>Definitions and limitations (${data.notes.length})</summary><ul>${data.notes.map(note => `<li>${esc(note)}</li>`).join("")}</ul></details>` : "";
}

function renderOverview(data, ctx) {
  const m = data.metrics, t = data.tables;
  ctx.metrics.innerHTML = metricCards([
    ["Teaching periods",m.offerings,"Count"],["Total number of students",m.assignment_students,"Distinct students in Canvas Assignments"],
    ["Students with Canvas activity",m.engagement_students,"Distinct students in Canvas Engagement"],
    ["Qualtrics survey responses",m.survey_completed_responses,"Completed responses"],
    ["Salesforce support cases",m.support_records,"Verified course-scoped cases"]
  ]);
  ctx.coverage.innerHTML = coverageMatrix(data.coverage);
  const feedback = `${gauges(t.survey_themes || [])}${nps((t.survey_nps || [])[0])}${details(t.survey_questions || [],"Survey question detail")}`;
  const supportRows = t.support_channels || [];
  ctx.tables.innerHTML = [
    panel("Students coverage by teaching period","Assignment and Canvas activity files can contain different groups of students.",groupedColumns(t.offering_comparison || [],["assignment_students","engagement_students"]),t.offering_comparison || [],true),
    panel("Teaching period dates","Confirmed start and end dates for each teaching period.",calendar(t.course_calendar || []),[],true),
    academic(t),
    panel("Qualtrics feedback overview","Theme agreement uses a 1–5 scale. NPS uses a −100 to +100 scale and its segment shares use percentages.",feedback,[...(t.survey_themes||[]),...(t.survey_nps||[])],true),
    (t.support_data_status||[]).length ? `<article class="attention-card"><strong>Needs attention · Support data excluded</strong><p>The supplied case export has no verified course field or enrolment link. Date overlap alone is not enough to attribute cases to this course.</p></article>` :
      panel("Salesforce support overview","Verified course-scoped cases by contact channel",`${metricCards([["Salesforce support cases",(t.support_summary||[])[0]?.metrics?.records,"Cases"],["Median response time",(t.support_summary||[])[0]?.metrics?.median_response_hours,"Hours"]])}${bars(supportRows,"records",row=>human(row.dimensions?.group||row.label))}`,supportRows,true)
  ].join("");
  ctx.notes.innerHTML = notes(data);
}

function issueList(rows, selected) {
  const filtered = selected === "all" ? rows : rows.filter(row => row.dimensions?.topic === selected), max = Math.max(...filtered.map(row => number(row,"records")||0),1);
  return `<div class="issue-list">${filtered.map(row => { const value=number(row,"records"); return `<article><div><span>${esc(human(row.dimensions?.topic))}</span><b>${value ?? "NA"}</b></div><p>${esc(row.label)}</p><i style="width:${value == null ? 0 : value/max*100}%"></i></article>`; }).join("")}</div>`;
}

function renderEngagement(data, ctx) {
  const t=data.tables, m=data.metrics;
  ctx.metrics.innerHTML=metricCards([["Students with Canvas activity",m.students,"Students"],["Total page views",m.views,"Views"],["Average views per student",m.views_per_student,"Views per student"],["Salesforce support cases",m.support_records,"Cases"]]);
  ctx.coverage.innerHTML="";
  const activity=t.activity_by_start_date||[];
  const deadlines=(t.assignment_deadlines||[]).map(row=>({period:row.dimensions?.period,date:row.dimensions?.deadline_date,label:row.dimensions?.assessment_key||row.label}));
  const metricLabels={views:"Page views (count)",students:"Students (count)"};
  const activityCharts=["views","students"].map(key=>`<section class="mini-viz"><h4>${metricLabels[key]}</h4>${lineChart(activity,key,{seriesKey:"category",yTitle:metricLabels[key],markers:deadlines})}</section>`).join("");
  const other=t.other_resource_types||[];
  const otherBreakdown=other.length?`<details class="embedded-details"><summary>Show Other Canvas areas</summary><p>Other combines Canvas areas outside course content and assessments.</p><div class="mini-grid">${["views","students"].map(key=>`<section class="mini-viz"><h4>${metricLabels[key]}</h4>${bars(other,key,row=>human(row.dimensions?.resource_type))}</section>`).join("")}</div>${details(other)}</details>`:"";
  const issues=t.support_issue_summaries||[], topics=[...new Set(issues.map(row=>row.dimensions?.topic).filter(Boolean))], selected=topics.includes(ctx.state.supportTopic)?ctx.state.supportTopic:"all";
  const issueButtons=`<div class="chips" id="issueTopics"><button data-topic="all" class="${selected==="all"?"active":""}">All topics</button>${topics.map(topic=>`<button data-topic="${esc(topic)}" class="${selected===topic?"active":""}">${esc(human(topic))}</button>`).join("")}</div><div id="issueList">${issueList(issues,selected)}</div>`;
  const supportAvailable=(t.support_summary||[]).length>0;
  ctx.tables.innerHTML=[
    panel("Where students engaged in Canvas","Students can appear in more than one Canvas area. Counts show students and page views.",`<div class="mini-grid">${["students","views"].map(key=>`<section class="mini-viz"><h4>${metricLabels[key]}</h4>${bars(t.resource_categories||[],key,row=>human(row.dimensions?.category))}</section>`).join("")}</div>${otherBreakdown}`,t.resource_categories||[],true),
    panel("Activity grouped by first access date","Each resource total is placed on the date it was first accessed. Dashed markers show AT1/AT2 deadlines.",`<div class="mini-grid">${activityCharts}</div>`,activity,true),
    panel("Page views by teaching week","Week 1 begins on the confirmed course start date.",lineChart(t.activity_by_course_week||[],"views",{seriesKey:"offering",numeric:true,aggregate:true,xTitle:"Teaching week",yTitle:"Total page views"}),t.activity_by_course_week||[],true),
    panel("Page views by learning stage","First-access activity before, during and after the confirmed teaching period.",heatmap(t.activity_by_course_phase||[],"offering","period","views",{aggregate:true}),t.activity_by_course_phase||[],true),
    supportAvailable?panel("Salesforce support summary","Verified course-scoped cases and confirmed response times.",metricCards([["Salesforce support cases",(t.support_summary||[])[0]?.metrics?.records,"Cases"],["Cases with response time",(t.support_summary||[])[0]?.metrics?.response_n,"Cases"],["Median response time",(t.support_summary||[])[0]?.metrics?.median_response_hours,"Hours"]]),t.support_summary||[]):"",
    supportAvailable?panel("Salesforce case status","Open, closed and unknown support cases.",bars(t.support_status||[],"records",row=>human(row.dimensions?.group)),t.support_status||[]):"",
    supportAvailable?panel("Salesforce support demand over time","Case counts and response time in hours use separate charts.",`<div class="mini-grid"><section class="mini-viz"><h4>Support cases (count)</h4>${lineChart(t.support_timeline||[],"records",{xKey:"group",yTitle:"Cases (count)"})}</section><section class="mini-viz"><h4>Median response time (hours)</h4>${lineChart(t.support_timeline||[],"median_response_hours",{xKey:"group",yTitle:"Hours"})}</section></div>`,t.support_timeline||[],true):"",
    supportAvailable?panel("Salesforce contact channels","Number of support cases by contact channel.",bars(t.support_channels||[],"records",row=>human(row.dimensions?.group)),t.support_channels||[]):"",
    supportAvailable?panel("Salesforce time to first response","Age (Hours) is the confirmed response-time field.",bars(t.support_response_distribution||[],"records",row=>human(row.dimensions?.group)),t.support_response_distribution||[]):"",
    supportAvailable?panel("Common Salesforce support needs","One case can match more than one keyword topic.",bars(t.support_topics||[],"records",row=>human(row.dimensions?.group)),t.support_topics||[]):"",
    supportAvailable?panel("Salesforce support topics over time","Darker cells represent more matched support cases.",heatmap(t.support_topics_timeline||[],"course","group","records",{parseRow:row=>String(row.dimensions?.group||"").split(":").slice(1).join(":"),parseColumn:row=>String(row.dimensions?.group||"").split(":")[0]}),t.support_topics_timeline||[],true):"",
    supportAvailable?panel("Salesforce support cases by weekday","Number of cases opened on each weekday.",bars([...(t.support_weekdays||[])].sort((a,b)=>Number(a.dimensions?.group)-Number(b.dimensions?.group)),"records",row=>["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][Number(row.dimensions?.group)]||row.label),t.support_weekdays||[]):"",
    supportAvailable?panel("Examples of Salesforce support requests","Frequent issue subjects grouped by topic after direct identifiers are removed.",issueButtons,issues,true):"",
    (t.support_data_status||[]).length ? `<article class="attention-card"><strong>Needs attention · Support data excluded</strong><p>This course export is filtered by date only and does not contain a verified course field or enrolment link.</p></article>` : ""
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

function renderAssignments(data,ctx) {
  const t=data.tables,m=data.metrics,assessments=t.assessments||[],groups=byOffering(assessments),sections=[];
  ctx.metrics.innerHTML=metricCards([["Total number of students",m.students,"Distinct students in Canvas Assignments"]]);
  ctx.coverage.innerHTML="";
  sections.push(`<section class="page-section"><header><h3>Assignment completion</h3><p>Submitted students out of all students with a record for each selected assignment.</p></header><div class="assignment-cards compact">${assessments.map(row=>{
    const name=assignmentName(row),fullName=row.label===name?"":`<p class="assignment-title">${esc(row.label)}</p>`;
    return `<article><span>${esc(shortOffering(row.dimensions.offering))}</span><h4>${esc(name)}</h4>${fullName}<div class="completion-ratio"><strong>${shown(row.metrics.submitted_students,0)} / ${shown(row.metrics.students,0)}</strong><span>students submitted</span></div></article>`;
  }).join("")}</div></section>`);
  for (const [offering,rows] of Object.entries(groups)) {
    const refs=new Set(rows.map(row=>row.dimensions.assignment_ref));
    const select=key=>(t[key]||[]).filter(row=>row.dimensions.offering===offering&&refs.has(row.dimensions.assignment_ref));
    const name=ref=>assignmentName(rows.find(row=>row.dimensions.assignment_ref===ref)||{label:"Unmapped assignment",dimensions:{}});
    const hasScored=rows.some(row=>row.dimensions.kind==="scored")&&ctx.state.mode!=="self_assessment";
    const scoredRefs=new Set(rows.filter(row=>row.dimensions.kind==="scored").map(row=>row.dimensions.assignment_ref));
    const passRows=select("assessment_pass_status").filter(row=>scoredRefs.has(row.dimensions.assignment_ref));
    const curveRows=select("assignment_cumulative_submission"),scheduleRows=select("assignment_schedule");
    const statusItems=rows.map(item=>{
      const source=select("submission_status").filter(row=>row.dimensions.assignment_ref===item.dimensions.assignment_ref);
      const count=bands=>source.filter(row=>bands.includes(row.dimensions.band)).reduce((sum,row)=>sum+(number(row,"students")||0),0);
      return {label:assignmentName(item),segments:[
        {label:"submitted",value:count(["submitted","graded"]),color:CATEGORY_COLORS.submitted},
        {label:"unsubmitted",value:count(["unsubmitted","missing"]),color:CATEGORY_COLORS.unsubmitted},
        {label:"excused",value:count(["excused","unknown"]),color:CATEGORY_COLORS.excused}
      ]};
    });
    const academicRows=(t.academic_results||[]).filter(row=>row.dimensions.offering===offering);
    sections.push(`<section class="page-section"><header><h3>${esc(shortOffering(offering))}</h3><p>Submission and Pass results for this teaching period.</p></header><div class="viz-grid">
      ${panel("Submission status","Submitted and graded are Canvas source states. Result availability is shown separately in Pass status.",stacked(statusItems),select("submission_status"),true)}
      ${panel("Number of attempts","Latest exported attempt number; a missing attempt stays unavailable.",assignmentDistribution(select("attempt_distribution"),name,{"1":"One attempt","2":"Two attempts","3_plus":"More than two attempts",unknown:"Attempt count unavailable"}),select("attempt_distribution"),true)}
      ${curveRows.length?panel("Cumulative submissions after the release proxy date","The source has no publication timestamp, so the earliest recorded Canvas created_at date is used as a clearly labelled proxy. The dashed line is the assignment deadline.",lineChart(curveRows,"submitted_pct",{xKey:"days_from_creation",seriesKey:"assignment_ref",seriesLabel:name,numeric:true,xTitle:"Calendar days since release proxy",yTitle:"Students submitted (%)",yMax:100,markers:scheduleRows.filter(row=>row.dimensions.deadline_days_from_creation!=="unknown").map(row=>({period:row.dimensions.deadline_days_from_creation,date:row.dimensions.deadline_date,label:`${row.dimensions.assessment_key} deadline`}))}),[...scheduleRows,...curveRows],true):panel("Cumulative submissions after the release proxy date","No usable created_at values are available for this selection.","",scheduleRows,true)}
      ${hasScored?panel("Assignment pass status","Passed means a valid result met the confirmed pass mark. Fail means a valid result was below the pass mark. Unavailable results are not counted as failures.",assignmentDistribution(passRows,name,{passed:"Passed",below_pass_mark:"Fail",result_unavailable:"Result unavailable"},{passed:"#438a69",below_pass_mark:"#c4515c",result_unavailable:"#8793a5"}),passRows,true):""}
      ${hasScored?academic({academic_results:academicRows}):""}
      ${select("self_assessment_completion").length?panel("Self-assessment completion","Completion means submitted or graded participation; these activities are not scored.",assignmentDistribution(select("self_assessment_completion"),name),select("self_assessment_completion"),true):""}
    </div></section>`);
  }
  if ((t.assignment_pair_submission||[]).length) {
    const pair=t.assignment_pair_submission[0].dimensions, left=assessments.find(row=>row.dimensions.assignment_ref===pair.first_assignment),right=assessments.find(row=>row.dimensions.assignment_ref===pair.second_assignment);
    const names={both_submitted:"Both submitted",first_only:`${assignmentName(left||{label:"First assignment"})} only`,second_only:`${assignmentName(right||{label:"Second assignment"})} only`,neither_submitted:"Neither submitted"};
    sections.push(panel("Completion across AT1 and AT2","Students are included when both assignment records are available.",bars(t.assignment_pair_submission,"students",row=>names[row.key]),t.assignment_pair_submission,true));
  }
  const badgeRows=t.badge_status||[], reconciliation=t.badge_course_reconciliation||[];
  if (badgeRows.length) {
    const badgeItems=[{label:"Assignment population",segments:badgeRows.map(row=>({label:row.key,value:number(row,"students"),color:CATEGORY_COLORS[row.key]}))}];
    const checkItems=[{label:"Assignment population",segments:reconciliation.map(row=>({label:row.key,value:number(row,"students"),color:CATEGORY_COLORS[row.key]||COLORS[0]}))}];
    const passedWithout=number(reconciliation.find(row=>row.key==="passed_no_badge_record"),"students");
    const badgeWithout=number(reconciliation.find(row=>row.key==="badge_recorded_pass_not_confirmed"),"students");
    sections.push(`<section class="page-section badge-section"><header><h3>Course completion and Badge records</h3><p>Confirmed course pass is shown above. Badge evidence is matched to the same Assignment population by student and teaching period.</p></header>${(passedWithout||badgeWithout)?`<article class="attention-card"><strong>Course pass and Badge records differ</strong><p>${passedWithout||0} passed students have no active Badge record; ${badgeWithout||0} active Badge records do not have a confirmed pass in the current assignment snapshot.</p></article>`:""}<div class="viz-grid">
      ${panel("Badge record status","Active, revoked, unmatched and review states. No Badge record does not mean the student failed.",stacked(badgeItems),badgeRows,true)}
      ${panel("Course pass and Badge check","Both measures use students with Assignment records. Differences are retained for review.",stacked(checkItems),reconciliation,true)}
      ${panel("Completion and Badge counts by teaching period","Student counts for the Assignment population, confirmed course passes and active Badge records.",groupedColumns(t.badge_offering_comparison||[],["total_students","confirmed_passes","active_badges"]),t.badge_offering_comparison||[],true)}
    </div></section>`);
  }
  ctx.tables.innerHTML=sections.join("");ctx.notes.innerHTML=notes(data);
}

const feedbackGroup = row => FEEDBACK_GROUPS[row.dimensions?.question_group] || human(row.dimensions?.question_group);

function feedbackResponseChart(rows) {
  return `<div class="feedback-columns">${groupedColumns(rows, ["responses"], feedbackGroup)}</div>`;
}

function feedbackTopChart(rows) {
  return `<div class="feedback-bars">${bars(rows, "responses", row => `${feedbackGroup(row)} top1 → ${human(row.label)}`, 20, () => COLORS[0])}</div>`;
}

function renderOutcomes(data,ctx){
  const t=data.tables,m=data.metrics;
  ctx.metrics.innerHTML=metricCards([["Qualtrics survey responses",m.survey_completed_responses,"Completed responses"]],true);
  ctx.coverage.innerHTML="";
  const offering=data.filters?.offering, scope=offering ? `Showing offering ${shortOffering(offering)}.` : "Showing all offerings combined; use the Offering selector to view one teaching period.";
  ctx.tables.innerHTML=`<div class="scope-note"><b>Qualtrics feedback scope</b><span>${esc(scope)}</span></div><div class="viz-grid">
    ${panel("Would students recommend the MicroCert?","NPS ranges from −100 to +100. Segment shares show the percentage of valid 0–10 responses.",(t.survey_nps||[]).map(row=>`<section class="nps-offering"><h4>${esc(shortOffering(row.dimensions?.offering))}</h4>${nps(row)}</section>`).join(""),t.survey_nps||[],true)}
    ${panel("Qualtrics theme scores","Mean agreement uses a 1–5 scale. Each completed response is weighted equally after meeting the theme answer requirement.",gauges(t.survey_themes||[]),t.survey_themes||[],true)}
    ${panel("Qualtrics question response distribution","Open Q1, Q3, Q4 or Q5 to compare every statement in that original question. Each group includes its own 1–5 colour key.",likert(t.survey_questions||[],t.survey_distribution||[]),[...(t.survey_questions||[]),...(t.survey_distribution||[])],true)}
    ${panel("Topic feedback statistics","Compares completed text responses across four feedback topics. A higher column means more students answered that topic.",feedbackResponseChart(t.survey_feedback_response_counts||[]),t.survey_feedback_response_counts||[],true)}
    ${panel("Most common feedback type in each area","Shows the highest-frequency classified feedback type within each area. This describes the leading request or theme, rather than sentiment.",feedbackTopChart(t.survey_feedback_topic_highlights||[]),t.survey_feedback_topics||[],true)}
    ${panel("Anonymous feedback comments","Comments appear only in View data below. Direct identifiers are removed and comments retain their feedback category.","<p class=\"folded-copy\">Open View data to read the cleaned comments by feedback category.</p>",t.survey_feedback_comments||[],true)}
  </div>`;
  ctx.notes.innerHTML=notes(data);
}

export function renderSpecialPage(data,{state,el}){
  const renderer={overview:renderOverview,engagement:renderEngagement,assignments:renderAssignments,outcomes:renderOutcomes}[data.page];
  if(!renderer)return false;
  const ctx={state,metrics:el("metrics"),coverage:el("coverage"),tables:el("tables"),notes:el("notes")};
  [ctx.metrics,ctx.coverage,ctx.tables,ctx.notes].forEach(node=>node.classList.add("special-page"));
  renderer(data,ctx);return true;
}

export function clearSpecialPage(el){["metrics","coverage","tables","notes"].forEach(id=>el(id).classList.remove("special-page"));}
