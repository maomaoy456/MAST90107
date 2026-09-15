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
  const match = String(code || "").match(/_(\d{4})_([A-Z]{3})_(PAR_\d+)$/);
  return match ? `${human(match[2]).slice(0, 3)} ${match[1]} · ${match[3].replace("_", " ")}` : String(code || "Unknown");
};
const rowLabel = row => row.dimensions?.offering ? shortOffering(row.dimensions.offering) : human(row.label || row.key);

function details(rows, title = "View data") {
  if (!rows?.length) return "";
  const dimensions = [...new Set(rows.flatMap(row => Object.keys(row.dimensions || {})))];
  const metrics = [...new Set(rows.flatMap(row => Object.keys(row.metrics || {})))];
  return `<details><summary>${esc(title)} (${rows.length} rows)</summary><div class="table-wrap"><table><thead><tr><th>Item</th>${dimensions.map(key => `<th>${esc(human(key))}</th>`).join("")}${metrics.map(key => `<th>${esc(human(key))}</th>`).join("")}</tr></thead><tbody>${rows.map(row =>
    `<tr><td>${esc(row.label)}</td>${dimensions.map(key => `<td>${esc(row.dimensions?.[key] ?? "—")}</td>`).join("")}${metrics.map(key => `<td>${shown(row.metrics?.[key], 2)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}

function panel(title, subtitle, body, rows = [], wide = false) {
  return `<article class="viz-panel${wide ? " wide" : ""}"><header><div><h3>${esc(title)}</h3>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div></header>${body || '<p class="empty">No data available for this selection.</p>'}${details(rows)}</article>`;
}

function metricCards(items, hero = false) {
  return `<div class="viz-metrics${hero ? " hero" : ""}">${items.map(([label, metric, context]) =>
    `<article class="viz-kpi"><span>${esc(label)}</span><strong>${shown(metric, 2)}</strong>${context ? `<small>${esc(context)}</small>` : ""}</article>`).join("")}</div>`;
}

function bars(rows, metric, labeler = rowLabel, limit = 20) {
  const items = rows.map(row => ({ row, value: number(row, metric) })).filter(item => item.value != null).slice(0, limit);
  if (!items.length) return "";
  const max = Math.max(...items.map(item => Math.abs(item.value)), 1);
  return `<div class="hbars">${items.map(({ row, value }) => `<div class="hbar"><span title="${esc(labeler(row))}">${esc(labeler(row))}</span><div><i style="width:${Math.abs(value) / max * 100}%"></i></div><b>${value.toLocaleString("en-AU", { maximumFractionDigits: 2 })}</b></div>`).join("")}</div>`;
}

function groupedColumns(rows, metrics, labeler = rowLabel) {
  const values = rows.flatMap(row => metrics.map(key => number(row, key))).filter(value => value != null);
  if (!values.length) return "";
  const max = Math.max(...values, 1);
  return `<div class="column-chart"><div class="column-groups">${rows.map(row => `<div class="column-group"><div class="columns">${metrics.map((key, index) => {
    const value = number(row, key);
    return `<i style="height:${value == null ? 0 : Math.max(value / max * 100, value ? 3 : 0)}%;background:${COLORS[index]}" title="${esc(human(key))}: ${value ?? "Not available"}"></i>`;
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

function lineChart(rows, metric, { xKey = "period", seriesKey, seriesLabel, numeric = false, aggregate = false } = {}) {
  const names = [...new Set(rows.map(row => seriesKey ? row.dimensions?.[seriesKey] : "All").filter(Boolean))].slice(0, 7);
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
  const max = Math.max(...values.values(), 1), width = 860, height = 260, left = 50, right = 20, top = 18, bottom = 44;
  const x = index => left + index * (width - left - right) / Math.max(periods.length - 1, 1);
  const y = value => top + (max - value) * (height - top - bottom) / max;
  const paths = names.map((name, index) => {
    const points = periods.map((period, i) => values.has(`${name}\u0000${period}`) ? `${x(i)},${y(values.get(`${name}\u0000${period}`))}` : null);
    const segments = []; let part = [];
    [...points, null].forEach(point => { if (point) part.push(point); else if (part.length) { segments.push(part); part = []; } });
    const dots = periods.map((period, i) => values.has(`${name}\u0000${period}`)
      ? `<circle cx="${x(i)}" cy="${y(values.get(`${name}\u0000${period}`))}" r="3.5" fill="${COLORS[index]}"><title>${esc(seriesLabel ? seriesLabel(name) : human(name))} · ${esc(period)}: ${values.get(`${name}\u0000${period}`)}</title></circle>` : "").join("");
    return segments.filter(segment => segment.length > 1).map(segment => `<polyline points="${segment.join(" ")}" fill="none" stroke="${COLORS[index]}" stroke-width="2"/>`).join("") + dots;
  }).join("");
  const ticks = [...new Set([0, Math.floor((periods.length - 1) / 2), periods.length - 1])];
  return `<div class="line-chart"><svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(human(metric))} over time"><line class="axis" x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}"/><line class="axis" x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}"/><text x="4" y="${top+5}">${max.toLocaleString("en-AU", {maximumFractionDigits:1})}</text><text x="25" y="${height-bottom+4}">0</text>${paths}${ticks.map(i => `<text x="${x(i)}" y="${height-14}" text-anchor="middle">${esc(periods[i])}</text>`).join("")}</svg><div class="legend">${names.map((name, index) => `<span><i style="background:${COLORS[index]}"></i>${esc(seriesLabel ? seriesLabel(name) : seriesKey === "offering" ? shortOffering(name) : human(name))}</span>`).join("")}</div></div>`;
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

function coverageTable(coverage) {
  const matrix = coverageMatrix(coverage);
  return matrix.replace(/^<article class="viz-panel wide"><h3>Data coverage<\/h3>/, "").replace(/<\/article>$/, "");
}

function calendar(rows) {
  const parsed = rows.map(row => ({ row, start: Date.parse(row.dimensions?.starts_on), end: Date.parse(row.dimensions?.ends_on) })).filter(item => Number.isFinite(item.start) && Number.isFinite(item.end));
  if (!parsed.length) return "";
  const min = Math.min(...parsed.map(item => item.start)), max = Math.max(...parsed.map(item => item.end)), span = Math.max(max - min, 1);
  return `<div class="calendar-list">${parsed.sort((a, b) => a.start-b.start).map(({row,start,end}) => `<div><span>${esc(shortOffering(row.dimensions.offering))}</span><div><i style="left:${(start-min)/span*100}%;width:${Math.max((end-start)/span*100,2)}%"></i></div><b>${esc(human(row.dimensions.phase))}</b></div>`).join("")}</div>`;
}

function gauges(rows) {
  return `<div class="gauge-grid">${rows.map((row, index) => {
    const value = number(row, "mean_agreement"), pct = value == null ? 0 : Math.max(0, Math.min(100, value / 5 * 100));
    return `<article><div class="gauge" style="--score:${pct}%;--colour:${COLORS[index % COLORS.length]}"><span>${value == null ? "NA" : value.toFixed(2)}<small>/5</small></span></div><b>${esc(human(row.dimensions?.theme || row.label))}</b><small>n = ${shown(row.metrics?.valid_responses)}</small></article>`;
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
    return `<div class="likert-row"><span title="${esc(question.label)}">${esc(question.label)}</span><div>${counts.map((value,index) => `<i style="width:${total ? value/total*100 : 0}%;background:${["#9f3131","#d77973","#898781","#78a9df","#245b99"][index]}" title="${index+1}: ${value}"></i>`).join("")}</div><b>${shown(question.metrics?.mean_agreement,2)}</b><small>n=${shown(question.metrics?.valid_responses)}</small></div>`;
  }).join("")}</div>`;
  const labels = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"];
  return chart + `<div class="legend likert-legend">${labels.map((label,index) => `<span><i style="background:${["#9f3131","#d77973","#898781","#78a9df","#245b99"][index]}"></i>${index+1} · ${label}</span>`).join("")}</div>`;
}

function academic(tables) {
  const rows = tables.academic_results || [], distribution = tables.weighted_grade_distribution || [];
  const resultItems = rows.map(row => ({ label: shortOffering(row.dimensions.offering), segments: [
    {label:"Passed",value:number(row,"passed"),color:"#438a69"}, {label:"Below threshold",value:number(row,"below_threshold"),color:"#c4515c"}, {label:"Unknown",value:number(row,"unknown"),color:"#8793a5"}
  ]}));
  return [panel("Academic outcomes", "Complete weighted results remain separate from Badge", stacked(resultItems), rows, true),
    panel("Weighted grade distribution", "Fixed grade bands by offering", heatmap(distribution,"offering","band","memberships"), distribution, true)].join("");
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
    panel("Course calendar","Teaching windows on a shared scale",calendar(t.course_calendar || []),t.course_calendar || [],true),
    academic(t),
    panel("Learner feedback","Theme agreement and recommendation NPS",feedback,[...(t.survey_themes||[]),...(t.survey_nps||[])],true),
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
  ctx.coverage.innerHTML=coverageMatrix(data.coverage);
  const activityKey=ctx.state.engagementAttribution || "activity_by_start_date", activity=t[activityKey]||[];
  const activityButtons=`<div class="switch" id="activitySwitch"><button data-value="activity_by_start_date" class="${activityKey==="activity_by_start_date"?"active":""}">First viewed</button><button data-value="activity_by_midpoint" class="${activityKey==="activity_by_midpoint"?"active":""}">Midpoint estimate</button></div>`;
  const activityCharts=["views","students","participations"].map(key=>`<section class="mini-viz"><h4>${human(key)}</h4>${lineChart(activity,key,{seriesKey:"category"})}</section>`).join("");
  const issues=t.support_issue_summaries||[], topics=[...new Set(issues.map(row=>row.dimensions?.topic).filter(Boolean))], selected=topics.includes(ctx.state.supportTopic)?ctx.state.supportTopic:"all";
  const issueButtons=`<div class="chips" id="issueTopics"><button data-topic="all" class="${selected==="all"?"active":""}">All topics</button>${topics.map(topic=>`<button data-topic="${esc(topic)}" class="${selected===topic?"active":""}">${esc(human(topic))}</button>`).join("")}</div><div id="issueList">${issueList(issues,selected)}</div>`;
  ctx.tables.innerHTML=[
    panel("Resource categories","Students overlap across categories",["students","views","participations"].map(key=>`<section class="mini-viz"><h4>${human(key)}</h4>${bars(t.resource_categories||[],key,row=>human(row.dimensions?.category))}</section>`).join(""),t.resource_categories||[],true),
    panel("Activity attribution","Choose one aggregate estimate; the two views must not be added",activityButtons+`<div class="mini-grid">${activityCharts}</div>`,activity,true),
    panel("Activity by course week","Views by offering, summed across resource categories",lineChart(t.activity_by_course_week||[],"views",{seriesKey:"offering",numeric:true,aggregate:true}),t.activity_by_course_week||[],true),
    panel("Activity by course phase","Views by offering and learning phase",heatmap(t.activity_by_course_phase||[],"offering","period","views",{aggregate:true}),t.activity_by_course_phase||[],true),
    panel("Support summary","Case records and confirmed response hours",metricCards([["Records",(t.support_summary||[])[0]?.metrics?.records],["Responses measured",(t.support_summary||[])[0]?.metrics?.response_n],["Median response hours",(t.support_summary||[])[0]?.metrics?.median_response_hours]]),t.support_summary||[]),
    panel("Support status","Open, closed and unknown records",bars(t.support_status||[],"records",row=>human(row.dimensions?.group)),t.support_status||[]),
    panel("Support records over time","Counts and response time use separate scales",`<div class="mini-grid"><section class="mini-viz"><h4>Case records</h4>${lineChart(t.support_timeline||[],"records",{xKey:"group"})}</section><section class="mini-viz"><h4>Median response hours</h4>${lineChart(t.support_timeline||[],"median_response_hours",{xKey:"group"})}</section></div>`,t.support_timeline||[],true),
    panel("Support channels","Records by contact channel",bars(t.support_channels||[],"records",row=>human(row.dimensions?.group)),t.support_channels||[]),
    panel("Response-time distribution","Age (Hours) is confirmed response time",bars(t.support_response_distribution||[],"records",row=>human(row.dimensions?.group)),t.support_response_distribution||[]),
    panel("Support topics","Keyword topics can overlap",bars(t.support_topics||[],"records",row=>human(row.dimensions?.group)),t.support_topics||[]),
    panel("Support topics over time","Darker cells represent more matched case records",heatmap(t.support_topics_timeline||[],"course","group","records",{parseRow:row=>String(row.dimensions?.group||"").split(":").slice(1).join(":"),parseColumn:row=>String(row.dimensions?.group||"").split(":")[0]}),t.support_topics_timeline||[],true),
    panel("Support records by weekday","Monday is 0 and Sunday is 6",bars([...(t.support_weekdays||[])].sort((a,b)=>Number(a.dimensions?.group)-Number(b.dimensions?.group)),"records",row=>["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"][Number(row.dimensions?.group)]||row.label),t.support_weekdays||[]),
    panel("Representative support issues","Frequent redacted issue subjects grouped by topic",issueButtons,issues,true),
    panel("Course calendar","Teaching windows for the selected scope",calendar(t.course_calendar||[]),t.course_calendar||[],true)
  ].join("");
  ctx.notes.innerHTML=notes(data);
  document.querySelectorAll("#activitySwitch button").forEach(button=>button.onclick=()=>{ctx.state.engagementAttribution=button.dataset.value;renderEngagement(data,ctx);});
  document.querySelectorAll("#issueTopics button").forEach(button=>button.onclick=()=>{ctx.state.supportTopic=button.dataset.topic;renderEngagement(data,ctx);});
}

function byOffering(rows) {
  return Object.groupBy ? Object.groupBy(rows,row=>row.dimensions?.offering||"Unknown") : rows.reduce((out,row)=>{const key=row.dimensions?.offering||"Unknown";(out[key]||=[]).push(row);return out;},{});
}
function assignmentName(row){return `${row.dimensions?.assessment_key&&row.dimensions.assessment_key!=="unconfirmed"?row.dimensions.assessment_key+" · ":""}${row.label}`;}
function assignmentBars(rows,metric="students"){return bars(rows,metric,row=>`${assignmentName(row)} · ${human(row.dimensions?.band)}`);}

function renderAssignments(data,ctx){
  const t=data.tables,m=data.metrics, assessments=t.assessments||[], groups=byOffering(assessments), sections=[];
  ctx.metrics.innerHTML=metricCards([["Assignment students",m.students],["Survey responses",m.survey_completed_responses]]);
  ctx.coverage.innerHTML=coverageMatrix(data.coverage);
  sections.push(`<section class="page-section"><header><h3>1. Assignment overview</h3><p>Participation, submission and available grades for the current API selection.</p></header><div class="assignment-cards">${assessments.map(row=>`<article><span>${esc(shortOffering(row.dimensions?.offering))}</span><h4>${esc(assignmentName(row))}</h4><div><b>${shown(row.metrics?.students)}</b><small>students</small><b>${shown(row.metrics?.submission_rate_pct,1,"%")}</b><small>submitted</small><b>${shown(row.metrics?.mean_score_pct,1,"%")}</b><small>mean score</small></div></article>`).join("")}</div>${details(assessments)}</section>`);
  for(const [offering,rows] of Object.entries(groups)){
    const refs=new Set(rows.map(row=>row.dimensions?.assignment_ref)), select=key=>(t[key]||[]).filter(row=>row.dimensions?.offering===offering&&refs.has(row.dimensions?.assignment_ref));
    const assignmentLabel=ref=>assignmentName(rows.find(row=>row.dimensions?.assignment_ref===ref)||{label:ref,dimensions:{}});
    const hasScored=rows.some(row=>row.dimensions?.kind==="scored") && ctx.state.mode!=="self_assessment";
    const statusItems=rows.map(item=>({label:assignmentName(item),segments:select("submission_status").filter(row=>row.dimensions.assignment_ref===item.dimensions.assignment_ref).map(row=>({label:row.dimensions.band,value:number(row,"students"),color:CATEGORY_COLORS[row.dimensions.band]}))}));
    const deadline=select("assignment_deadline_coverage");
    const academicRows=(t.academic_results||[]).filter(row=>row.dimensions?.offering===offering);
    const weightedRows=(t.weighted_grade_distribution||[]).filter(row=>row.dimensions?.offering===offering);
    sections.push(`<section class="page-section"><header><h3>${esc(shortOffering(offering))}</h3><p>${esc(offering)}</p></header>
      <div class="viz-grid">${panel("Completion and submission status","Submission, missing and late values remain independent",stacked(statusItems),select("submission_status"),true)}
      ${panel("Missing flag","Source missing marker",assignmentBars(select("missing_flag")),select("missing_flag"))}${panel("Late flag","Source late marker",assignmentBars(select("late_flag")),select("late_flag"))}
      ${panel("Attempt distribution","Null attempts remain unknown",assignmentBars(select("attempt_distribution")),select("attempt_distribution"),true)}
      ${deadline.length?panel("Deadline coverage","Whether each deadline is observed at the current reporting date",assignmentBars(deadline),deadline,true):""}
      ${panel("Cumulative submission","Days relative to each deadline",lineChart(select("assignment_cumulative_submission"),"submitted_pct",{xKey:"days_relative_to_deadline",seriesKey:"assignment_ref",seriesLabel:assignmentLabel,numeric:true}),select("assignment_cumulative_submission"),true)}
      ${panel("Submission timing","Negative values are early; positive values are late",assignmentBars(select("assignment_submission_timing")),select("assignment_submission_timing"))}
      ${panel("Late duration","Only rows marked late use the supplied duration",assignmentBars(select("late_duration")),select("late_duration"))}
      ${panel("Deadline and grading summary","Eligibility, final-day submission and grading intervals",metricCards(select("assignment_time_summary").flatMap(row=>[[`${row.label}: final 24h`,row.metrics.final_24h_pct_among_submitted],[`${row.label}: median relative days`,row.metrics.median_days_relative_to_deadline],[`${row.label}: median grading days`,row.metrics.median_grading_days]])),select("assignment_time_summary"),true)}
      ${hasScored?panel("Assignment score distribution","Valid graded work only",assignmentBars(select("score_distribution")),select("score_distribution")):""}
      ${hasScored?panel("Weighted grade distribution","Confirmed AT1 40% and AT2 60% rule",bars(weightedRows,"memberships",row=>human(row.dimensions?.band)),weightedRows):""}
      ${hasScored?panel("Weighted outcomes","Complete grades only; unknown is not zero",metricCards(academicRows.flatMap(row=>[["Pass rate",row.metrics.pass_rate_among_complete_pct],["Mean weighted grade",row.metrics.mean_weighted_pct],["Complete grades",row.metrics.complete_grades],["Unknown",row.metrics.unknown]])),academicRows,true):""}
      ${select("self_assessment_completion").length?panel("Self-assessment activity","Completion is participation, not a score",assignmentBars(select("self_assessment_completion")),select("self_assessment_completion"),true):""}</div></section>`);
  }
  if((t.survey_themes||[]).length) sections.push(`<section class="page-section"><header><h3>Assessment feedback</h3><p>Completed Survey responses mapped to assessment questions.</p></header>${panel("Assessment theme","Fixed 0–5 agreement scale",gauges(t.survey_themes||[]),t.survey_themes||[])}${panel("Assessment questions","Response distribution and mean agreement",likert(t.survey_questions||[],t.survey_distribution||[]),[...(t.survey_questions||[]),...(t.survey_distribution||[])],true)}</section>`);
  if((t.assignment_pair_submission||[]).length) sections.push(`<section class="page-section"><header><h3>Selected assignment pair</h3></header>${panel("Submission combination","Only available when exactly two assignments in one offering are selected",bars(t.assignment_pair_submission,"students",row=>human(row.key)),t.assignment_pair_submission,true)}</section>`);
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
    academic:academic(t)+panel("Course calendar","Teaching windows and current phase",calendar(t.course_calendar||[]),t.course_calendar||[],true),
    survey:[panel("Survey coverage","Survey data is explicitly mapped by offering",coverageTable(data.coverage),[],true),panel("Would they recommend it?","NPS composition",nps((t.survey_nps||[])[0]),t.survey_nps||[]),panel("Survey theme scores","Average agreement on a fixed 0–5 scale",gauges(t.survey_themes||[]),t.survey_themes||[],true),panel("Question response distribution","Diverging Likert-style distribution",likert(t.survey_questions||[],t.survey_distribution||[]),[...(t.survey_questions||[]),...(t.survey_distribution||[])],true),panel("Feedback topics","Keyword categories can overlap",bars(t.survey_feedback_topics||[],"responses",row=>`${human(row.dimensions?.question_group)} · ${human(row.label)}`),t.survey_feedback_topics||[],true),panel("Anonymous feedback comments","Direct identifiers are removed before display",comments(t.survey_feedback_comments||[]),t.survey_feedback_comments||[],true)].join(""),
    diagnostics:[panel("Award diagnostics","Reasons records could or could not be matched",bars(t.award_diagnostics||[],"records",row=>human(row.label)),t.award_diagnostics||[],true),coverageMatrix(data.coverage),panel("Source snapshots","Latest completed source snapshots",`<div class="snapshot-list">${Object.entries(data.snapshots||{}).map(([key,value])=>`<div><span>${esc(human(key))}</span><b>${esc(value)}</b></div>`).join("")}</div>`,[],true),notes(data)].join("")
  };
  ctx.tables.innerHTML=`<div class="outcome-tabs" id="outcomeTabs">${[["badge","Badge"],["academic","Academic results"],["survey","Survey"],["diagnostics","Diagnostics"]].map(([key,label])=>`<button data-tab="${key}" class="${tab===key?"active":""}">${label}</button>`).join("")}</div><div class="viz-grid">${panels[tab]}</div>`;
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
