import { chartCopy } from "./chart-copy.js?v=20260930-7";

const scopeParams = (course, offering) => ({course, ...(offering ? {offering} : {})});
const responseKey = params => `/v1/insight-notes?${new URLSearchParams(Object.entries(params).sort(([a],[b])=>a.localeCompare(b)))}`;
const noteId = note => [note.course,note.offering,note.chart_key].join("|");
const slug = text => text.toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_|_$/g,"");
const hash = text => [...text].reduce((n,c)=>Math.imul(n^c.charCodeAt(0),16777619)>>>0,2166136261).toString(36);
const COURSE_SCOPE_TITLES = new Set([
  "Page views by teaching week", "Page views by learning stage"
]);

export function createChartNotes({api, state, snapshot, showMessage}) {
  const saved = new Map(), drafts = new Map(), loaded = new Set();
  const storageKey = `mpe-chart-notes:${snapshot?.meta?.generated_at || "live"}`;
  const remember = note => {
    saved.set(noteId(note),note);
    if (!snapshot) return;
    const key = responseKey(scopeParams(note.course,note.offering));
    const payload = snapshot.responses[key] ||= {notes:[]};
    payload.notes = payload.notes.filter(item=>item.chart_key!==note.chart_key).concat(note);
  };
  if (snapshot) {
    Object.entries(snapshot.responses).filter(([key])=>key.startsWith("/v1/insight-notes?")).forEach(([,payload])=>{
      (payload.notes || (payload.chart_key ? [payload] : [])).forEach(note=>saved.set(noteId(note),note));
    });
    try {
      Object.values(JSON.parse(localStorage.getItem(storageKey)||"{}")).forEach(note=>{
        const previous=saved.get(noteId(note));
        if (!previous || Date.parse(note.updated_at)>Date.parse(previous.updated_at||0)) remember(note);
      });
    } catch { /* The HTML copy is the portable persistence path. */ }
  }

  async function load() {
    const courseOfferings=(state.catalog?.offerings||[]).filter(item=>item.course===state.course).map(item=>item.code);
    const offerings=["insights","data-rules"].includes(state.page) ? [""] : state.page==="engagement"
      ? [...new Set(["",...courseOfferings])] : [...new Set([state.offering,""])];
    for (const offering of offerings) {
      const key=responseKey(scopeParams(state.course,offering));
      if (loaded.has(key)) continue;
      const result=await api(key);
      for (const note of result.notes) saved.set(noteId(note),note);
      loaded.add(key);
    }
  }

  function enhance() {
    const cards=[...document.querySelectorAll("#coverage .viz-panel:not(.notes), #tables .viz-panel:not(.notes), #tables .visual, #tables .mini-viz, #tables .model-card, #tables .survey-question-group, #tables .assignment-cards article")];
    for (const card of cards) {
      if (card.querySelector(":scope > .key-insight")) continue;
      const heading=card.querySelector(":scope > header h3, :scope > h3, :scope > h4, :scope > summary");
      if (!heading) continue;
      const title=heading.textContent.trim();
      const parent=card.parentElement.closest(".viz-panel")?.querySelector("h3")?.textContent || "";
      const detail=card.closest("details.embedded-details")?.querySelector(":scope > summary")?.textContent?.trim() || "";
      const context=state.page==="insights" ? state.insightsTab : "";
      let key = `${state.page}.${slug([parent,detail,title].filter(Boolean).join("_")).slice(0,95)}${context?"."+context:""}`;
      if (title==="When do learners submit after an assignment is released?") key="assignment_submission_timing";
      if (key.length>160) key=key.slice(0,145)+"."+hash(key);
      card.dataset.chartKey=key;
      if (card.classList.contains("model-card") && card.closest(".model-summary-panel")) continue;
      const copy=chartCopy[title] || (card.classList.contains("model-card")
        ? ["Outcome counts and model validation scores.","Compare model quality before interpreting predictions."]
        : card.classList.contains("survey-question-group")
        ? ["Response counts for each statement below.","Compare agreement and disagreement within this question."]
        : card.matches(".assignment-cards article")
        ? ["Submitted students out of assignment records.","Check how many learners have a recorded submission."]
        : [parent?`${title} for this comparison.`:"Values for the current selection.",chartCopy[parent]?.[1] || "Compare the available evidence for this selection."]);
      if (!heading.parentElement.querySelector(":scope > .chart-subtitle")) {
        const old=heading.nextElementSibling;
        if (old?.tagName==="P" && !old.matches(".empty,.rule-note,.assignment-title,.chart-note")) old.remove();
        const subtitle=document.createElement("p"), caption=document.createElement("p");
        subtitle.className="chart-subtitle"; subtitle.textContent=copy[0];
        caption.className="chart-purpose"; caption.textContent=copy[1];
        const anchor=card.classList.contains("model-card") ? card.querySelector("header") : heading;
        anchor.after(subtitle,caption);
      }
      // Child charts need their own interpretation; avoid a second editor on the wrapper panel.
      const hasNestedComparison = !card.classList.contains("model-summary-panel") && card.classList.contains("viz-panel") && Boolean(card.querySelector(
        ":scope .mini-viz, :scope .visual, :scope .model-card, :scope .survey-question-group, :scope .assignment-cards article"));
      if (hasNestedComparison) continue;
      const offering=state.page==="insights" || COURSE_SCOPE_TITLES.has(title) || COURSE_SCOPE_TITLES.has(parent) ? "" : state.offering;
      const scope={course:state.course,offering,chart_key:key}, id=noteId(scope);
      const inherited=offering==="" ? [...saved.values()].filter(item=>item.course===state.course
        &&(item.chart_key===key||(title==="Page views by teaching week"&&item.chart_key.startsWith(key+".")))
        &&item.offering&&item.note)
        .sort((a,b)=>Date.parse(b.updated_at||0)-Date.parse(a.updated_at||0))[0] : null;
      const existing=saved.get(id)||inherited,note=existing?.note||"";
      const editor=document.createElement("section"); editor.className="key-insight";
      editor.innerHTML='<div class="key-insight-heading"><strong>Key insight</strong></div><div class="insight-editor"><p class="insight-text"></p><details><summary>Edit insight</summary><textarea maxlength="2000" rows="2" aria-label="Key insight note"></textarea><div class="key-insight-actions"><span role="status"></span><button type="button">Save note</button></div></details></div>';
      const input=editor.querySelector("textarea"), status=editor.querySelector('[role="status"]'), button=editor.querySelector("button"), text=editor.querySelector(".insight-text");
      input.setAttribute("aria-label",`Key insight: ${title}`);
      input.value=drafts.has(id)?drafts.get(id):note;
      text.textContent=note||"Add an insight to explain what this comparison means.";
      status.textContent=drafts.has(id)&&drafts.get(id)!==note?"Unsaved changes":saved.has(id)?"Saved":inherited?"Reused across this course":"Not saved";
      input.oninput=()=>{drafts.set(id,input.value);status.textContent="Unsaved changes";};
      button.onclick=async()=>{
        button.disabled=true;status.textContent="Saving…";
        const entered=input.value;
        try {
          const result=snapshot ? {...scope,note:entered,updated_at:new Date().toISOString()}
            : await api("/v1/insight-notes",{method:"PUT",body:JSON.stringify({...scope,note:entered})});
          remember(result);
          if (input.value===entered) drafts.delete(id);
          text.textContent=entered||"Add an insight to explain what this comparison means.";
          status.textContent=input.value===entered?"Saved":"Unsaved changes";
          if(snapshot) {
            try {localStorage.setItem(storageKey,JSON.stringify(Object.fromEntries(saved)));}
            catch {status.textContent="Saved in this page. Download HTML to keep it.";}
          }
        } catch(error) {status.textContent=error.message;} finally {button.disabled=false;}
      };
      card.append(editor);
    }
  }

  async function download() {
    if ([...drafts].some(([id,note])=>note!==(saved.get(id)?.note||""))) {
      showMessage("Save your edited insight notes before downloading the HTML."); return;
    }
    const button=document.getElementById("downloadInsightHtml"); button.disabled=true;
    try {
      let copy=document.documentElement.cloneNode(true);
      // The hosted static directory needs its embedded-asset shell; offline HTML already has inline assets.
      if (!copy.querySelector("#dashboardSnapshot")) {
        const response=await fetch("offline-shell.html");
        if (!response.ok) throw new Error("The offline HTML template could not be loaded.");
        copy=new DOMParser().parseFromString(await response.text(),"text/html").documentElement;
      }
      const script=copy.querySelector("#dashboardSnapshot");
      const payload=JSON.stringify(snapshot).replace(/</g,"\\u003c").replace(/\u2028/g,"\\u2028").replace(/\u2029/g,"\\u2029");
      script.textContent=`window.__MPE_STATIC_SNAPSHOT__=${payload};`;
      const url=URL.createObjectURL(new Blob(["<!doctype html>\n",copy.outerHTML],{type:"text/html;charset=utf-8"}));
      const link=document.createElement("a");link.href=url;link.download="MPE-dashboard-with-insights.html";
      document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
      showMessage("The downloaded HTML includes all saved notes across courses and pages.");
    } catch(error) {showMessage(error.message);} finally {button.disabled=false;}
  }
  return {load,enhance,download};
}
