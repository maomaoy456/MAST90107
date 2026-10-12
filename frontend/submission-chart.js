// Shape-preserving curves: connect observations without overshooting their counts.
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[c]);
const seriesLabel = key => key === "AT1" ? "Assessment 1 (AT1)" : key === "AT2" ? "Assessment 2 (AT2)" : key;

function collectSeries(rows, schedules) {
  return schedules.map(schedule => {
    const d=schedule.dimensions,key=d.assessment_key,anomaly=d.deadline_status==="source_date_after_course_end";
    const points=rows
      .filter(row=>row.dimensions.assignment_ref===d.assignment_ref&&row.metrics.submitted_students?.value!=null)
      .map(row=>({x:Number(row.dimensions.days_from_deadline),y:row.metrics.submitted_students.value}))
      .filter(point=>Number.isFinite(point.x)).sort((a,b)=>a.x-b.x);
    return {key,name:d.assignment_name,points,anomaly,deadlineDate:d.deadline_date,
      anomalyDays:Number(d.deadline_days_after_course_end)||0,colour:key==="AT2"?"#d9792b":"#2878b5"};
  }).filter(item=>item.points.length);
}

function chartSvg(series) {
  if(!series.length)return '<p class="empty">Select at least one assessment with a source deadline and dated submissions.</p>';
  const points=series.flatMap(item=>item.points),min=Math.min(0,...points.map(p=>p.x)),max=Math.max(0,...points.map(p=>p.x));
  const ceiling=Math.max(5,Math.ceil(Math.max(...points.map(p=>p.y))/5)*5);
  const x=day=>76+(day-min)/(max-min||1)*690,y=count=>260-count/ceiling*198;
  const ticks=Array.from({length:6},(_,i)=>Math.round(min+(max-min)*i/5));
  const paths=series.map((item,index)=>{
    const path=item.points.map((p,i)=>{
      if(!i)return `M ${x(p.x)} ${y(p.y)}`;
      const previous=item.points[i-1],middle=(x(previous.x)+x(p.x))/2;
      return `C ${middle} ${y(previous.y)}, ${middle} ${y(p.y)}, ${x(p.x)} ${y(p.y)}`;
    }).join(" ");
    const square=item.key==="AT2",last=item.points.at(-1);
    const overlap=series.some((other,j)=>j<index&&Math.abs(y(other.points.at(-1).y)-y(last.y))<18&&Math.abs(x(other.points.at(-1).x)-x(last.x))<80);
    return `<path d="${path}" fill="none" stroke="${item.colour}" stroke-width="${square?2.5:3}" ${square?'stroke-dasharray="7 4"':""}/>`+
      item.points.map(p=>`${square?`<rect x="${x(p.x)-3}" y="${y(p.y)-3}" width="6" height="6"`:`<circle cx="${x(p.x)}" cy="${y(p.y)}" r="3.5"`} fill="${item.colour}"><title>${esc(item.key)} · Day ${p.x}: ${p.y} submissions</title>${square?"</rect>":"</circle>"}`).join("")+
      `<text x="${x(last.x)+8}" y="${y(last.y)+(overlap?20:4)}" fill="${item.colour}" font-weight="700">${esc(item.key)} ${last.y}</text>`;
  }).join("");
  const tickValues=[...new Set([...ticks,0])].sort((a,b)=>a-b);
  return `<svg viewBox="0 0 860 330" role="img" aria-label="Cumulative submissions aligned to each assignment deadline">
    ${Array.from({length:6},(_,i)=>ceiling*i/5).map(v=>`<line x1="76" x2="766" y1="${y(v)}" y2="${y(v)}" stroke="#e7edf3"/><text x="65" y="${y(v)+4}" text-anchor="end">${v}</text>`).join("")}
    <line x1="${x(0)}" x2="${x(0)}" y1="62" y2="260" stroke="#64748b" stroke-dasharray="5 4"/><text x="${Math.max(150,Math.min(690,x(0)))}" y="42" text-anchor="middle">Day 0 · each assignment's deadline</text>
    ${paths}${tickValues.map(v=>`<text x="${x(v)}" y="282" text-anchor="middle">${v}</text>`).join("")}
    <text transform="translate(19 165) rotate(-90)" text-anchor="middle">Cumulative submissions (count)</text>
    <text x="420" y="315" text-anchor="middle">Days before / after each assignment deadline</text></svg>`;
}

export function submissionChart(rows,schedules) {
  const series=collectSeries(rows,schedules);
  if(!series.length)return '<p class="empty">A source deadline and dated submission records are needed for this comparison.</p>';
  const preferred=series.filter(item=>!item.anomaly),selected=new Set((preferred.length?preferred:[series[0]]).map(item=>item.key));
  const controls=series.map(item=>`<button type="button" class="submission-series-toggle${selected.has(item.key)?" selected":""}" data-series-key="${esc(item.key)}" aria-pressed="${selected.has(item.key)}"><i style="background:${item.colour}"></i><span>${esc(seriesLabel(item.key))}${item.anomaly?' <small>Deadline requires review</small>':""}</span></button>`).join("");
  const warnings=series.filter(item=>item.anomaly).map(item=>`<div class="deadline-warning"><strong>${esc(item.key)} deadline requires review</strong><span>The source deadline ${esc(item.deadlineDate)} is ${item.anomalyDays} days after the teaching period ended. This curve is available from the legend but is hidden by default.</span></div>`).join("");
  return `<div class="submission-chart" data-submission-series="${esc(JSON.stringify(series))}">
    <div class="submission-series-controls" aria-label="Assessments shown">${controls}</div>
    <div class="submission-plot">${chartSvg(series.filter(item=>selected.has(item.key)))}</div>
    ${warnings}<p class="chart-note">Each line starts at the first observed submission. Negative days are before the source deadline; positive days are after it. Smooth lines connect observed totals and do not estimate time spent working.</p></div>`;
}

export function bindSubmissionCharts(root=document) {
  root.querySelectorAll(".submission-series-toggle").forEach(button=>{
    if(button.dataset.submissionChartBound)return;
    button.dataset.submissionChartBound="true";
    button.addEventListener("click",()=>{
    const chart=button.closest("[data-submission-series]"),buttons=[...chart.querySelectorAll(".submission-series-toggle")];
    const active=button.getAttribute("aria-pressed")==="true";
    if(active&&buttons.filter(item=>item.getAttribute("aria-pressed")==="true").length===1)return;
    button.setAttribute("aria-pressed",String(!active));
    button.classList.toggle("selected",!active);
    const selected=new Set(buttons.filter(item=>item.getAttribute("aria-pressed")==="true").map(item=>item.dataset.seriesKey));
    const series=JSON.parse(chart.dataset.submissionSeries);
    chart.querySelector(".submission-plot").innerHTML=chartSvg(series.filter(item=>selected.has(item.key)));
    });
  });
}
