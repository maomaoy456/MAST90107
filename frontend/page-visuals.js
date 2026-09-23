"use strict";

const COLORS = ["#2878b5", "#d9792b", "#438a69", "#8057a5", "#c4515c", "#4b8795", "#768399"];
const BAND_LABELS = {
  below_70: "Below 70", "70_to_below_80": "70–<80", "80_and_above": "80 and above",
  unknown: "Unknown", yes: "Yes", no: "No", submitted: "Submitted", unsubmitted: "Unsubmitted",
  graded: "Graded", excused: "Excused", not_late: "Not late", no_observed_submission: "No submission",
  content: "Content", assessment: "Assessment", other: "Other Canvas areas",
  discussions: "Discussions", user_profiles: "User/profile pages", announcements: "Announcements",
  calendar_events: "Calendar events", external_tools: "External tools", grades: "Grades",
  passed: "Passed", below_pass_mark: "Did not reach pass mark", result_unavailable: "Result unavailable",
  passed_and_badge: "Passed and Badge recorded", passed_no_badge_record: "Passed, no Badge record",
  badge_recorded_pass_not_confirmed: "Badge recorded, pass not confirmed", neither_confirmed: "Neither confirmed",
  valid: "Active Badge recorded", revoked_only: "Revoked Badge only",
  needs_review: "Teaching period could not be confirmed", no_matched_award: "No Badge record found",
  cohort_students: "Students represented", confirmed_course_passes: "Confirmed course passes",
  valid_award_holders: "Students with an active Badge", assignment_students: "Students with assignment records",
  engagement_students: "Students with Canvas activity", revoked: "Revoked Badge",
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
      <dt>Did not reach pass mark</dt><dd>${below??"NA"}</dd>
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
    ["Teaching periods",m.offerings,"Selected course"],["Students with assignment records",m.assignment_students,"Distinct students"],
    ["Students with Canvas activity",m.engagement_students,"Distinct students"],["Students linked across Canvas sources",m.intersection_students,"Matched student IDs"],
    ["Survey responses",m.survey_completed_responses,"Completed responses"],["Support cases",m.support_records,"Verified course-scoped cases"]
  ]);
  ctx.coverage.innerHTML = coverageMatrix(data.coverage);
  const feedback = `${gauges(t.survey_themes || [])}${nps((t.survey_nps || [])[0])}${details(t.survey_questions || [],"Survey question detail")}`;
  const supportRows = t.support_channels || [];
  ctx.tables.innerHTML = [
    panel("Students coverage by teaching period","Assignment and Canvas activity files can contain different groups of students.",groupedColumns(t.offering_comparison || [],["assignment_students","engagement_students"]),t.offering_comparison || [],true),
    panel("Teaching period dates","Confirmed start and end dates for each teaching period.",calendar(t.course_calendar || []),[],true),
    academic(t),
    panel("Students feedback overview","Theme agreement uses completed questionnaires with at least half the theme items answered; recommendation uses its own valid-response count",feedback,[...(t.survey_themes||[]),...(t.survey_nps||[])],true),
    (t.support_data_status||[]).length ? `<article class="attention-card"><strong>Needs attention · Support data excluded</strong><p>The supplied case export has no verified course field or enrolment link. Date overlap alone is not enough to attribute cases to this course.</p></article>` :
      panel("Support demand overview","Verified course-scoped cases by contact channel",`${metricCards([["Support cases",(t.support_summary||[])[0]?.metrics?.records],["Median response hours",(t.support_summary||[])[0]?.metrics?.median_response_hours]])}${bars(supportRows,"records",row=>human(row.dimensions?.group||row.label))}`,supportRows,true)
  ].join("");
  ctx.notes.innerHTML = notes(data);
}

function issueList(rows, selected) {
  const filtered = selected === "all" ? rows : rows.filter(row => row.dimensions?.topic === selected), max = Math.max(...filtered.map(row => number(row,"records")||0),1);
  return `<div class="issue-list">${filtered.map(row => { const value=number(row,"records"); return `<article><div><span>${esc(human(row.dimensions?.topic))}</span><b>${value ?? "NA"}</b></div><p>${esc(row.label)}</p><i style="width:${value == null ? 0 : value/max*100}%"></i></article>`; }).join("")}</div>`;
}

function renderEngagement(data, ctx) {
  const t=data.tables, m=data.metrics;
  ctx.metrics.innerHTML=metricCards([["Students with Canvas activity",m.students],["Total page views",m.views],["Interactive actions",m.participations],["Average views per student",m.views_per_student],["Support cases",m.support_records]]);
  ctx.coverage.innerHTML="";
  const activity=t.activity_by_start_date||[];

  const metricLabels={views:"Total page views",students:"Students",participations:"Interactive actions"};
  const activityCharts=["views","students","participations"].map(key=>`<section class="mini-viz"><h4>${metricLabels[key]}</h4>${lineChart(activity,key,{seriesKey:"category",yTitle:metricLabels[key]})}</section>`).join("");
  const other=t.other_resource_types||[];
  const otherBreakdown=other.length?`<details class="embedded-details"><summary>Show Other Canvas areas</summary><p>Other combines Canvas areas outside course content and assessments.</p><div class="mini-grid">${["views","students","participations"].map(key=>`<section class="mini-viz"><h4>${metricLabels[key]}</h4>${bars(other,key,row=>human(row.dimensions?.resource_type))}</section>`).join("")}</div>${details(other)}</details>`:"";
  const issues=t.support_issue_summaries||[], topics=[...new Set(issues.map(row=>row.dimensions?.topic).filter(Boolean))], selected=topics.includes(ctx.state.supportTopic)?ctx.state.supportTopic:"all";
  const issueButtons=`<div class="chips" id="issueTopics"><button data-topic="all" class="${selected==="all"?"active":""}">All topics</button>${topics.map(topic=>`<button data-topic="${esc(topic)}" class="${selected===topic?"active":""}">${esc(human(topic))}</button>`).join("")}</div><div id="issueList">${issueList(issues,selected)}</div>`;
  const supportAvailable=(t.support_summary||[]).length>0;
  ctx.tables.innerHTML=[
    panel("Where Students engaged in Canvas","Students can appear in more than one category.",`<div class="mini-grid">${["students","views","participations"].map(key=>`<section class="mini-viz"><h4>${metricLabels[key]}</h4>${bars(t.resource_categories||[],key,row=>human(row.dimensions?.category))}</section>`).join("")}</div>${otherBreakdown}`,t.resource_categories||[],true),
    panel("Activity grouped by first access date","Each resource summary’s full count is assigned to its first access date. This is not a daily click log.",`<div class="mini-grid">${activityCharts}</div>`,activity,true),
    panel("Page views by teaching week","Week 1 begins on the confirmed course start date.",lineChart(t.activity_by_course_week||[],"views",{seriesKey:"offering",numeric:true,aggregate:true,xTitle:"Teaching week",yTitle:"Total page views"}),t.activity_by_course_week||[],true),
    panel("Page views by learning stage","First-access activity before, during and after the confirmed teaching period.",heatmap(t.activity_by_course_phase||[],"offering","period","views",{aggregate:true}),t.activity_by_course_phase||[],true),
    supportAvailable?panel("Support summary","Verified course-scoped cases and confirmed response hours",metricCards([["Support cases",(t.support_summary||[])[0]?.metrics?.records],["Responses measured",(t.support_summary||[])[0]?.metrics?.response_n],["Median response hours",(t.support_summary||[])[0]?.metrics?.median_response_hours]]),t.support_summary||[]):"",
    supportAvailable?panel("Support status","Open, closed and unknown support cases",bars(t.support_status||[],"records",row=>human(row.dimensions?.group)),t.support_status||[]):"",
    supportAvailable?panel("Support demand over time","Support case counts and response hours use separate scales.",`<div class="mini-grid"><section class="mini-viz"><h4>Support cases</h4>${lineChart(t.support_timeline||[],"records",{xKey:"group"})}</section><section class="mini-viz"><h4>Median response hours</h4>${lineChart(t.support_timeline||[],"median_response_hours",{xKey:"group"})}</section></div>`,t.support_timeline||[],true):"",
    supportAvailable?panel("How Students contacted support","Support cases by contact channel.",bars(t.support_channels||[],"records",row=>human(row.dimensions?.group)),t.support_channels||[]):"",
    supportAvailable?panel("Time to first response","Age (Hours) is the confirmed response time field.",bars(t.support_response_distribution||[],"records",row=>human(row.dimensions?.group)),t.support_response_distribution||[]):"",
    supportAvailable?panel("Common support needs","One case can match more than one keyword topic.",bars(t.support_topics||[],"records",row=>human(row.dimensions?.group)),t.support_topics||[]):"",
    supportAvailable?panel("Support topics over time","Darker cells represent more matched support cases",heatmap(t.support_topics_timeline||[],"course","group","records",{parseRow:row=>String(row.dimensions?.group||"").split(":").slice(1).join(":"),parseColumn:row=>String(row.dimensions?.group||"").split(":")[0]}),t.support_topics_timeline||[],true):"",
    supportAvailable?panel("Support cases by weekday","Monday is 0 and Sunday is 6",bars([...(t.support_weekdays||[])].sort((a,b)=>Number(a.dimensions?.group)-Number(b.dimensions?.group)),"records",row=>["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][Number(row.dimensions?.group)]||row.label),t.support_weekdays||[]):"",
    supportAvailable?panel("Examples of common support requests","Frequent issue subjects grouped by topic after direct identifiers are removed.",issueButtons,issues,true):"",
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

function submissionTimeSummary(rows, name) {
  return `<div class="result-summaries">${rows.map(row=>`<article><h4>${esc(name(row.dimensions.assignment_ref))}</h4><dl>
    <dt>Students with a submission time</dt><dd>${shown(row.metrics.students_with_submission_time,0)}</dd>
    <dt>Median days from course start</dt><dd>${shown(row.metrics.median_days_from_course_start,1)}</dd>
    <dt>Middle 50% of submissions</dt><dd>${shown(row.metrics.q1_days_from_course_start,1)} to ${shown(row.metrics.q3_days_from_course_start,1)} days</dd>
  </dl><small>This is elapsed calendar time, not time spent working.</small></article>`).join("")}</div>`;
}

function renderAssignments(data,ctx) {
  const t=data.tables,m=data.metrics,assessments=t.assessments||[],groups=byOffering(assessments),sections=[];
  ctx.metrics.innerHTML=metricCards([["Students with assignment records",m.students,"Distinct students across the selected assignments"]]);
  ctx.coverage.innerHTML="";
  sections.push(`<section class="page-section"><header><h3>Assessment completion overview</h3><p>Pass rates use valid results. Unavailable results are shown separately and are not treated as failures.</p></header><div class="assignment-cards">${assessments.map(row=>{
    const name=assignmentName(row),fullName=row.label===name?"":`<p class="assignment-title">${esc(row.label)}</p>`;
    const outcome = row.dimensions.kind === "self_assessment" ? '<small>Non-scored activity</small>' : `<b>${shown(row.metrics.pass_rate_pct,1,"%")}</b><small>pass rate among valid results</small>`;
    return `<article><span>${esc(shortOffering(row.dimensions.offering))}</span><h4>${esc(name)}</h4>${fullName}<div class="assignment-kpis"><div><b>${shown(row.metrics.students,0)}</b><small>Students with a record</small></div><div><b>${shown(row.metrics.submission_rate_pct,1,"%")}</b><small>Submission rate</small></div><div>${outcome}</div></div></article>`;
  }).join("")}</div></section>`);
  for (const [offering,rows] of Object.entries(groups)) {
    const refs=new Set(rows.map(row=>row.dimensions.assignment_ref));
    const select=key=>(t[key]||[]).filter(row=>row.dimensions.offering===offering&&refs.has(row.dimensions.assignment_ref));
    const name=ref=>assignmentName(rows.find(row=>row.dimensions.assignment_ref===ref)||{label:"Unmapped assignment",dimensions:{}});
    const hasScored=rows.some(row=>row.dimensions.kind==="scored")&&ctx.state.mode!=="self_assessment";
    const scoredRefs=new Set(rows.filter(row=>row.dimensions.kind==="scored").map(row=>row.dimensions.assignment_ref));
    const passRows=select("assessment_pass_status").filter(row=>scoredRefs.has(row.dimensions.assignment_ref));
    const timeRows=select("assignment_submission_time"),timeDistribution=select("assignment_submission_time_distribution");
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
    sections.push(`<section class="page-section"><header><h3>${esc(shortOffering(offering))}</h3><p>Submission, Pass and timing results for this teaching period.</p></header><div class="viz-grid">
      ${panel("Submission status","Submitted and graded are source states. Result availability is shown separately in Pass status.",stacked(statusItems),select("submission_status"),true)}
      ${panel("Number of attempts","Latest exported attempt number; a missing attempt stays unavailable.",assignmentDistribution(select("attempt_distribution"),name,{"1":"One attempt","2":"Two attempts","3_plus":"More than two attempts",unknown:"Attempt count unavailable"}),select("attempt_distribution"),true)}
      ${timeRows.length?panel("Time to submission from course start","This is elapsed calendar time, not time spent working on the assessment.",submissionTimeSummary(timeRows,name)+assignmentDistribution(timeDistribution,name,{before_course_start:"Before course start",week_1:"Week 1",week_2:"Week 2",weeks_3_4:"Weeks 3–4",week_5_or_later:"Week 5 or later"}),[...timeRows,...timeDistribution],true):""}
      ${hasScored?panel("Assessment pass status","Passed means the valid result met the confirmed pass mark. Unavailable results are not treated as failures.",assignmentDistribution(passRows,name,{passed:"Passed",below_pass_mark:"Did not reach pass mark",result_unavailable:"Result unavailable"},{passed:"#438a69",below_pass_mark:"#c4515c",result_unavailable:"#8793a5"}),passRows,true):""}
      ${hasScored?academic({academic_results:academicRows}):""}
      ${select("self_assessment_completion").length?panel("Self-assessment completion","Completion means submitted or graded participation; these activities are not scored.",assignmentDistribution(select("self_assessment_completion"),name),select("self_assessment_completion"),true):""}
    </div></section>`);
  }
  if ((t.assignment_pair_submission||[]).length) {
    const pair=t.assignment_pair_submission[0].dimensions, left=assessments.find(row=>row.dimensions.assignment_ref===pair.first_assignment),right=assessments.find(row=>row.dimensions.assignment_ref===pair.second_assignment);
    const names={both_submitted:"Both submitted",first_only:`${assignmentName(left||{label:"First assignment"})} only`,second_only:`${assignmentName(right||{label:"Second assignment"})} only`,neither_submitted:"Neither submitted"};
    sections.push(panel("Completion across AT1 and AT2","Students are included when both assignment records are available.",bars(t.assignment_pair_submission,"students",row=>names[row.key]),t.assignment_pair_submission,true));
  }
  ctx.tables.innerHTML=sections.join("");ctx.notes.innerHTML=notes(data);
}

function comments(rows){
  const groups=byOffering(rows.map(row=>({...row,dimensions:{...row.dimensions,offering:row.dimensions?.question_group||"Other"}})));
  return `<div class="comment-groups">${Object.entries(groups).map(([group,items],index)=>`<details ${index===0?"open":""}><summary>${esc(human(group))} <span>${items.length} comments</span></summary>${items.map(row=>`<article><p>${esc(row.label)}</p><span>${shown(row.metrics?.responses)} response${number(row,"responses")===1?"":"s"}</span></article>`).join("")}</details>`).join("")}</div>`;
}

function renderOutcomes(data,ctx){
  const t=data.tables,m=data.metrics, tab=ctx.state.outcomesTab||"badge";
  ctx.metrics.innerHTML=metricCards([["Recorded Badge rate",m.badge_completion_rate_pct,"Active Badge / Students represented"],["Students represented",m.cohort_memberships,"Each student is counted once per teaching period"],["Students with an active Badge",m.valid_award_holders],["Students with a revoked Badge only",m.revoked_only_holders],["Survey responses",m.survey_completed_responses]],true);
  ctx.coverage.innerHTML="";
  const badgeItems=[{label:"Selected cohort",segments:(t.badge_status||[]).map(row=>({label:row.key,value:number(row,"memberships"),color:CATEGORY_COLORS[row.key]}))}];
  const reconciliation=t.badge_course_reconciliation||[],passedWithout=number(reconciliation.find(row=>row.key==="passed_no_badge_record"),"students"),badgeWithout=number(reconciliation.find(row=>row.key==="badge_recorded_pass_not_confirmed"),"students");
  const attention=(passedWithout||badgeWithout)?`<article class="attention-card"><strong>Needs attention · Course pass and Badge records differ</strong><p>${passedWithout||0} passed students have no active Badge record; ${badgeWithout||0} active Badge records do not have a confirmed pass in the current assignment snapshot.</p></article>`:"";
  const reconciliationItems=[{label:"Students represented",segments:reconciliation.map(row=>({label:row.key,value:number(row,"students"),color:CATEGORY_COLORS[row.key]||COLORS[0]}))}];
  const panels={
    badge:[attention,panel("Badge record status","Active, revoked, unmatched and review states. No Badge record does not mean the student failed.",stacked(badgeItems),t.badge_status||[],true),panel("Course pass and Badge check","Both measures use the same Canvas activity population. Differences remain visible and are not manually adjusted.",stacked(reconciliationItems),reconciliation,true),panel("Badge records by teaching period","Students represented, confirmed passes and active Badge records.",groupedColumns(t.offering_comparison||[],["cohort_students","confirmed_course_passes","valid_award_holders"]),t.offering_comparison||[],true),panel("Recorded Badge rate","Active matched Badge records divided by Students represented.",bars(t.offering_comparison||[],"badge_completion_rate_pct"),t.offering_comparison||[]),panel("Badges recorded over time","Active and revoked Badge records by issue date.",lineChart(t.award_timeline||[],"memberships",{seriesKey:"status",yTitle:"Badge records"}),t.award_timeline||[],true),panel("Time from course end to Badge issue","Negative values represent Badges issued before the confirmed course end date.",bars(t.badge_delay_from_course_end||[],"holders",row=>`${shortOffering(row.dimensions?.offering)} · ${human(row.dimensions?.band)}`),t.badge_delay_from_course_end||[],true)].join(""),
    academic:academic(t),
    survey:[panel("Would they recommend it?","NPS composition",nps((t.survey_nps||[])[0]),t.survey_nps||[]),panel("Survey theme scores","Agreement responses use 1–5. Valid responses count completed questionnaires with at least half of that theme’s items answered; each questionnaire is weighted equally.",gauges(t.survey_themes||[]),t.survey_themes||[],true),panel("Question response distribution","Each item uses its own valid-answer count. Counts can differ because questions were skipped; theme and item counts are not the same denominator.",likert(t.survey_questions||[],t.survey_distribution||[]),[...(t.survey_questions||[]),...(t.survey_distribution||[])],true),panel("Feedback topics","Keyword categories can overlap",bars(t.survey_feedback_topics||[],"responses",row=>`${human(row.dimensions?.question_group)} · ${human(row.label)}`),t.survey_feedback_topics||[],true),panel("Anonymous feedback comments","Direct identifiers are removed before display",comments(t.survey_feedback_comments||[]),t.survey_feedback_comments||[],true)].join(""),
    diagnostics:[panel("Data checks","Reasons Badge records could or could not be matched",bars(t.award_diagnostics||[],"records",row=>human(row.label)),t.award_diagnostics||[],true),panel("Source snapshots","Latest completed source snapshots",`<div class="snapshot-list">${Object.entries(data.snapshots||{}).map(([key,value])=>`<div><span>${esc(human(key))}</span><b>${esc(value)}</b></div>`).join("")}</div>`,[],true),notes(data)].join("")
  };
  const offering=data.filters?.offering, scope=offering ? `Showing offering ${shortOffering(offering)}.` : "Showing all offerings combined; use the Offering selector to view one teaching period.";
  ctx.tables.innerHTML=`<div class="scope-note"><b>Population included</b><span>${esc(scope)}</span></div><div class="outcome-tabs" id="outcomeTabs">${[["badge","Badge"],["academic","Course completion"],["survey","Survey"],["diagnostics","Data checks"]].map(([key,label])=>`<button data-tab="${key}" class="${tab===key?"active":""}">${label}</button>`).join("")}</div><div class="viz-grid">${panels[tab]}</div>`;
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
