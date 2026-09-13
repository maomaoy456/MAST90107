"""Two-course assignment analysis (quiz/self-assessment excluded).

Install: python -m pip install pandas numpy matplotlib scipy openpyxl
Run: python assignment_analysis.py --as-of 2026-09-13
Optional: --input PATH --output-dir PATH --timezone Australia/Melbourne

Default input/output are relative to this script, not the current directory.
Without --as-of, the latest observed submission/grading/enrolment timestamp is
used as a provisional observation cutoff, NOT a verified export timestamp.
Date-only cutoffs include the entire date in --timezone. All calculations use
timezone-aware timestamps. Plots use English to avoid platform font problems.

Functions return dataframes/figures for reuse by notebooks or frontend callers.
Associations are descriptive (no causal claims or unadjusted significance tests).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BASE = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE / 'Datasets' / 'canvas_assignment_activity_all_courses_anonymised.xlsx'
KEY = ['course_name', 'course_canvas_id', 'Student_ID_anonymised']
LABELS = ['Both submitted', 'A1 only', 'A2 only', 'Neither submitted']
PATTERNS = ['Both on time', 'A1 late only', 'A2 late only', 'Both late']
COLORS = {'A1': '#2878B5', 'A2': '#D9792B'}
TREATY = 'Understanding Treaty'
TIME_COLS = ['submitted_at', 'graded_at', 'due_at', 'created_at', 'updated_at']


def load_assignment_data(path: str | Path, as_of: str | None = None,
                         timezone: str = 'Australia/Melbourne'):
    """Read, validate, and select positive-point A1/A2 records without editing input."""
    raw = pd.read_excel(path)
    required = set(KEY + TIME_COLS + ['assignment_name', 'assignment_id',
                   'points_possible', 'score', 'submission_status', 'enrolment_status'])
    absent = required - set(raw.columns)
    if absent:
        raise ValueError(f'Missing columns: {sorted(absent)}')
    warnings = []
    for col in TIME_COLS:
        original = raw[col]
        raw[col] = pd.to_datetime(original, utc=True, errors='coerce')
        bad = int((original.notna() & raw[col].isna()).sum())
        if bad:
            warnings.append(f'{col}: {bad} invalid timestamps treated as missing.')
    if as_of:
        cutoff = pd.Timestamp(as_of)
        if cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize(timezone)
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', as_of):
            cutoff = cutoff + pd.DateOffset(days=1) - pd.Timedelta(nanoseconds=1)
        cutoff = cutoff.tz_convert('UTC')
        cutoff_source = 'User supplied; date-only inputs include the whole local day'
    else:
        cutoff = raw[['submitted_at', 'graded_at', 'created_at', 'updated_at']].max().max()
        if pd.isna(cutoff):
            raise ValueError('Cannot infer observation cutoff; supply --as-of.')
        cutoff_source = 'Latest observed event timestamp (provisional)'
        warnings.append('Observation cutoff is inferred, not a verified export date. '
                        'Rerun with --as-of once the export date is confirmed.')
    raw['points_possible'] = pd.to_numeric(raw.points_possible, errors='coerce')
    raw['score'] = pd.to_numeric(raw.score, errors='coerce')
    raw['assessment'] = raw.assignment_name.astype(str).str.extract(
        r'(?i)\b(?:Assessment(?:\s+Task)?|AT|A)\s*([12])\b', expand=False).map({'1': 'A1', '2': 'A2'})
    selection = (raw.points_possible > 0) & raw.assessment.notna()
    d = raw.loc[selection].copy()
    if 'course_code' not in d.columns or d.course_code.isna().any():
        raise ValueError('course_code is required for term selection.')
    d['term_id'] = d.course_code.astype(str)
    d['term_label'] = d.term_id.str.replace(r'^[^_]+_', '', regex=True).str.replace('_', ' ', regex=False)
    if d.empty:
        raise ValueError('No positive-point A1/A2 records found.')
    if d[KEY].isna().any().any():
        raise ValueError('Missing student/course identifiers; pairing is unsafe.')
    if d.duplicated(KEY + ['assessment']).any():
        raise ValueError('Duplicate student/course/A1-A2 keys; resolve before pairing.')
    d['due_eligible'] = d.due_at.notna() & (d.due_at <= cutoff)
    d['submitted'] = d.submitted_at.notna() & (d.submitted_at <= cutoff)
    d['graded_observed_at'] = d.graded_at.where(d.graded_at <= cutoff)
    d['score_observed'] = d.score.notna() & d.graded_observed_at.notna()
    d['score_pct'] = (100 * d.score / d.points_possible).where(d.score_observed)
    d['lead_days'] = ((d.due_at - d.submitted_at).dt.total_seconds() / 86400).where(d.submitted)
    d['late_derived'] = d.lead_days.lt(0).where(d.submitted & d.due_at.notna())
    d['grading_days'] = ((d.graded_at - d.submitted_at).dt.total_seconds() / 86400).where(
        d.submitted & d.graded_at.notna() & (d.graded_at <= cutoff))
    negative = d.grading_days.lt(0)
    if negative.any():
        warnings.append(f'{int(negative.sum())} negative grading intervals excluded.')
        d.loc[negative, 'grading_days'] = np.nan
    if d.score.notna().any() and ((d.score < 0) | (d.score > d.points_possible)).any():
        warnings.append('Scores outside 0..points_possible detected; inspect data_quality.csv.')
    warnings += [
        'submitted_at is a recorded submission timestamp; first versus latest attempt is unverified.',
        'Submission time is not work duration; no reliable assignment start time is available.',
        'graded_at may differ from the time grades/feedback became visible to students.',
        'No imputation of missing scores; course outcomes require two observed scores.',
        'Overall views pool offerings; Treaty also supports separate full course-code term views.',
        'Associations can reflect offering, assignment difficulty, extensions and selection effects.',
        'All enrolment statuses are included; inactive counts are reported separately.',
        'A historical cutoff cannot reconstruct overwritten submissions, deadlines or enrolment status.',
    ]
    metadata = dict(input=str(Path(path).resolve()), raw_rows=len(raw), selected_rows=len(d),
                    excluded_rows=int((~selection).sum()), as_of_utc=cutoff.isoformat(),
                    as_of_local=cutoff.tz_convert(timezone).isoformat(),
                    cutoff_source=cutoff_source, timezone=timezone, warnings=warnings)
    return d, metadata


def get_term_options(data: pd.DataFrame, course: str) -> list[dict]:
    """Frontend options: value=None is overall; full codes distinguish PAR classes."""
    g = data[data.course_name.eq(course)]
    if g.empty:
        raise ValueError(f'Unknown course: {course}')
    options = [{'value': None, 'label': '整体 / All terms'}]
    if course == TREATY:
        terms = g[['term_id', 'term_label']].drop_duplicates().copy()
        # Chronological sorting, retaining PAR suffixes within each month.
        months = {m: i for i, m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'], 1)}
        def sort_key(code):
            match = re.search(r'_(\d{4})_([A-Z]{3})_PAR_(\d+)$', code)
            return (int(match[1]), months.get(match[2], 99), int(match[3])) if match else (9999,99,code)
        for row in sorted(terms.to_dict('records'), key=lambda r: sort_key(r['term_id'])):
            options.append({'value': row['term_id'], 'label': row['term_label']})
    return options


def analyze_selection(data: pd.DataFrame, course: str, term: str | None = None,
                      include_figures: bool = True) -> dict:
    """Filter BEFORE pairing/statistics; frontend owns and closes returned figures."""
    options = get_term_options(data, course)
    allowed = {o['value']: o['label'] for o in options}
    if term not in allowed:
        raise ValueError(f'Invalid term for {course}: {term}')
    selected = data[data.course_name.eq(course)].copy()
    if term is not None:
        selected = selected[selected.term_id.eq(term)].copy()
    selected.attrs['view_label'] = allowed[term]
    pairs = build_student_pairs(selected)
    tables, summary = summarize_course(selected, pairs)
    summary.update(term_id=term, term_label=allowed[term])
    notices = []
    n = int((selected.due_eligible & selected.lead_days.abs().gt(60)).sum())
    if n:
        notices.append(f'{n} 条已到期作业的提交时间距截止日期超过 60 天，请核实截止日期后解释时间指标。')
    return {'records': selected, 'pairs': pairs, 'tables': tables, 'summary': summary,
            'notices': notices, 'figures': plot_course(selected, pairs, tables) if include_figures else {}}


def build_student_pairs(data: pd.DataFrame) -> pd.DataFrame:
    """One row per student-course enrolment; never pair across offerings."""
    values = ['due_eligible', 'submitted', 'lead_days', 'score_pct', 'submitted_at',
              'graded_observed_at', 'grading_days']
    parts = []
    for a in ['A1', 'A2']:
        part = data[data.assessment.eq(a)].set_index(KEY)[values].add_suffix('_' + a)
        parts.append(part)
    p = parts[0].join(parts[1], how='outer').reset_index()
    for a in ['A1', 'A2']:
        for col in ['due_eligible', 'submitted']:
            p[f'{col}_{a}'] = p[f'{col}_{a}'].eq(True)
    p['pair_eligible'] = p.due_eligible_A1 & p.due_eligible_A2
    p['both_submitted'] = p.submitted_A1 & p.submitted_A2
    p['completion'] = np.select(
        [p.both_submitted, p.submitted_A1, p.submitted_A2], LABELS[:3], default=LABELS[3])
    p['lead_change_days'] = (p.lead_days_A2 - p.lead_days_A1).where(p.both_submitted)
    p['score_change'] = p.score_pct_A2 - p.score_pct_A1
    p['weighted_score'] = .4 * p.score_pct_A1 + .6 * p.score_pct_A2
    p['outcome'] = np.select([p.weighted_score.ge(70), p.weighted_score.lt(70)],
                             ['Pass', 'Fail'], default='Unknown')
    a, b = p.lead_days_A1.lt(0), p.lead_days_A2.lt(0)
    p['timing_pattern'] = np.select([a & b, a, b],
        ['Both late', 'A1 late only', 'A2 late only'], default='Both on time')
    p.loc[~p.both_submitted | p.lead_days_A1.isna() | p.lead_days_A2.isna(), 'timing_pattern'] = 'Unknown'
    p['feedback_interval_days'] = ((p.submitted_at_A2 - p.graded_observed_at_A1).dt.total_seconds()/86400).where(p.submitted_A2)
    return p


def safe_spearman(frame, x, y, question):
    v = frame[[x, y]].dropna()
    valid = len(v) >= 3 and v[x].nunique() > 1 and v[y].nunique() > 1
    return dict(question=question, n=len(v), spearman_rho=float(spearmanr(v[x], v[y]).statistic)
                if valid else np.nan, note='Descriptive; no independence or causal claim' if valid
                else 'Insufficient pairs or constant variable')


def summarize_course(data, pairs):
    """Tables use overdue records; paired analyses require both assignments due."""
    e = data[data.due_eligible].copy()
    p = pairs[pairs.pair_eligible].copy()
    rows = []
    for a in ['A1', 'A2']:
        g = e[e.assessment.eq(a)]
        s = g[g.submitted]
        lead = s.lead_days.dropna()
        rows.append(dict(assessment=a, eligible_records=len(g), submitted=int(g.submitted.sum()),
            submission_rate=g.submitted.mean(), unsubmitted=int((~g.submitted).sum()),
            late_submissions=int(lead.lt(0).sum()), late_rate_among_submitted=lead.lt(0).mean(),
            final_24h_count=int(lead.between(0, 1, inclusive='both').sum()),
            final_24h_rate_among_submitted=lead.between(0, 1, inclusive='both').mean(),
            lead_days_median=lead.median(), lead_days_q25=lead.quantile(.25), lead_days_q75=lead.quantile(.75),
            score_n=int(g.score_pct.count()), score_mean=g.score_pct.mean(),
            grading_n=int(g.grading_days.count()), grading_days_median=g.grading_days.median(),
            inactive_records=int(g.enrolment_status.eq('inactive').sum())))
    completion = p.completion.value_counts().reindex(LABELS, fill_value=0).rename_axis('completion').reset_index(name='n')
    completion['proportion'] = completion.n / len(p) if len(p) else np.nan
    outcomes = p.outcome.value_counts().reindex(['Pass', 'Fail', 'Unknown'], fill_value=0).rename_axis('outcome').reset_index(name='n')
    known = p.weighted_score.notna()
    outcome_by_pattern = []
    for pattern in PATTERNS + ['Unknown']:
        g = p[p.timing_pattern.eq(pattern)]
        k = g[g.weighted_score.notna()]
        outcome_by_pattern.append(dict(timing_pattern=pattern, enrolments=len(g), known_outcomes=len(k),
            unknown_outcomes=int(g.weighted_score.isna().sum()), passes=int(k.outcome.eq('Pass').sum()),
            pass_rate_known=k.outcome.eq('Pass').mean(), weighted_score_mean=k.weighted_score.mean()))
    assoc = [safe_spearman(e[e.assessment.eq(a)], 'lead_days', 'score_pct', f'{a}: lead time vs score') for a in ['A1','A2']]
    assoc += [safe_spearman(p, 'lead_days_A1','lead_days_A2','A1 vs A2 lead time'),
              safe_spearman(p, 'lead_change_days','score_change','Change in lead time vs change in score'),
              safe_spearman(p, 'lead_days_A1','weighted_score','A1 lead time vs weighted score'),
              safe_spearman(p, 'lead_days_A2','weighted_score','A2 lead time vs weighted score')]
    summary = dict(course=str(data.course_name.iloc[0]), selected_records=len(data),
        unique_students=int(data.Student_ID_anonymised.nunique()), enrolments=len(pairs),
        not_yet_due_records=int((data.due_at.notna() & ~data.due_eligible).sum()),
        missing_deadline_records=int(data.due_at.isna().sum()), eligible_paired_enrolments=len(p),
        both_submitted=int(p.both_submitted.sum()), known_outcomes=int(known.sum()),
        unknown_outcomes=int((~known).sum()), pass_rate_known=p.loc[known,'outcome'].eq('Pass').mean(),
        weighted_score_mean=p.weighted_score.mean(), lead_change_n=int(p.lead_change_days.count()),
        lead_change_median=p.lead_change_days.median(), score_change_mean=p.score_change.mean(),
        feedback_interval_n=int(p.feedback_interval_days.count()),
        feedback_before_A2_rate=p.loc[p.feedback_interval_days.notna(),'feedback_interval_days'].ge(0).mean())
    return {'assignment_summary': pd.DataFrame(rows), 'completion': completion,
            'outcomes': outcomes, 'outcome_by_timing': pd.DataFrame(outcome_by_pattern),
            'associations': pd.DataFrame(assoc)}, summary


def _scatter(ax, frame, x, y, xlabel, ylabel, title):
    v = frame[[x, y]].dropna()
    ax.scatter(v[x], v[y], alpha=.6, s=24, color='#2878B5')
    r = safe_spearman(v, x, y, title)['spearman_rho']
    stat = f'rho={r:.2f}' if pd.notna(r) else 'rho unavailable'
    ax.set(title=f'{title}\nn={len(v)}, {stat}', xlabel=xlabel, ylabel=ylabel)
    ax.grid(alpha=.2)


def plot_course(data, pairs, tables):
    """Return identical six figure types for every course, even with sparse data."""
    e = data[data.due_eligible]
    p = pairs[pairs.pair_eligible]
    course = str(data.course_name.iloc[0])
    if data.attrs.get('view_label'):
        course += ' | ' + ('All terms' if data.attrs['view_label'].startswith('整体') else data.attrs['view_label'])
    figures = {}
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
    c = tables['completion']
    axes[0].barh(c.completion, c.n, color='#2878B5')
    for i, n in enumerate(c.n): axes[0].text(n, i, f' {n}', va='center')
    axes[0].set(title=f'Completion (both deadlines passed), n={len(p)}', xlabel='Student-course enrolments')
    s = tables['assignment_summary'].set_index('assessment')
    axes[1].bar(['A1','A2'], s.submission_rate * 100, color=list(COLORS.values()))
    axes[1].set(ylim=(0, 105), ylabel='Submitted / all eligible records (%)', title='Assignment submission rate')
    for i, a in enumerate(['A1','A2']): axes[1].text(i, 4, f"{int(s.loc[a,'submitted'])}/{int(s.loc[a,'eligible_records'])}", ha='center')
    fig.suptitle(course); figures['01_completion'] = fig

    fig, axes = plt.subplots(1,2, figsize=(12,4.8), sharex=True, layout='constrained')
    all_delay = -e.loc[e.submitted,'lead_days'].dropna()
    # Integer-day centres: the deadline bin spans [-0.5, +0.5) days.
    # Shared A1/A2 edges ensure zero is a bin centre, never a bin edge.
    first = min(0, int(np.floor(all_delay.min()))) if len(all_delay) else -1
    last = max(0, int(np.ceil(all_delay.max()))) if len(all_delay) else 1
    bins = np.arange(first - .5, last + 1.5, 1.)
    for a,color in COLORS.items():
        g = e[e.assessment.eq(a)]
        lead = g.loc[g.submitted,'lead_days'].dropna()
        delay = np.sort(-lead.to_numpy())
        axes[0].hist(delay, bins=bins, alpha=.5, label=f'{a} (n={len(lead)})', color=color)
        if len(delay):
            axes[1].step(np.r_[bins[0],delay,bins[-1]],
                         np.r_[0,np.arange(1,len(delay)+1)/len(g)*100,len(delay)/len(g)*100],
                         where='post', label=a,color=color)
    time_label = 'Days relative to deadline (negative = early; positive = late)'
    axes[0].set(xlabel=time_label,ylabel='Submitted records',title='Submission timing (1-day bins centred on whole days)')
    axes[1].set(xlabel=time_label,ylabel='Cumulative submitted / eligible (%)',ylim=(0,105),title='Cumulative submission; unsubmitted stay in denominator')
    tick_step = max(1, int(np.ceil((last-first)/8)))
    ticks = np.arange(np.ceil(first/tick_step)*tick_step, last+1, tick_step)
    axes[0].set_xticks(ticks)
    axes[0].set_xlim(bins[0], bins[-1])
    for ax in axes: ax.axvline(0,color='black',ls='--',lw=1); ax.legend(); ax.grid(alpha=.2)
    fig.suptitle(course); figures['02_submission_timing'] = fig

    fig, axes = plt.subplots(1,2, figsize=(12,4.8), layout='constrained')
    _scatter(axes[0],p,'lead_days_A1','lead_days_A2','A1 days before deadline','A2 days before deadline','Submission timing stability')
    lims = [min(axes[0].get_xlim()[0],axes[0].get_ylim()[0]),max(axes[0].get_xlim()[1],axes[0].get_ylim()[1])]
    axes[0].plot(lims,lims,'--',color='gray',label='Same lead time'); axes[0].legend()
    counts = p[p.both_submitted].timing_pattern.value_counts().reindex(PATTERNS,fill_value=0)
    matrix = np.array([[counts['Both on time'], counts['A2 late only']], [counts['A1 late only'],counts['Both late']]])
    axes[1].imshow(matrix,cmap='Blues'); axes[1].set(xticks=[0,1],xticklabels=['On time','Late'],yticks=[0,1],yticklabels=['On time','Late'],xlabel='A2',ylabel='A1',title='Submission transitions (paired submissions)')
    for i in range(2):
        for j in range(2): axes[1].text(j,i,str(matrix[i,j]),ha='center',va='center',color='white' if matrix[i,j]>matrix.max()/2 else 'black',fontsize=16)
    fig.suptitle(course); figures['03_paired_timing'] = fig

    fig, axes = plt.subplots(1,3, figsize=(16,4.8), layout='constrained')
    for ax,a in zip(axes[:2],['A1','A2']):
        _scatter(ax,e[e.assessment.eq(a)],'lead_days','score_pct','Days before deadline','Score / 100',a+': timing and score')
    _scatter(axes[2],p,'lead_change_days','score_change','Change in days early (A2 - A1)','Score change (A2 - A1)','Changes in timing and score')
    axes[2].axhline(0,color='gray',ls='--'); axes[2].axvline(0,color='gray',ls='--')
    fig.suptitle(course+' | Descriptive associations'); figures['04_timing_and_scores'] = fig

    fig, axes = plt.subplots(1,2, figsize=(12,4.8), layout='constrained')
    scores = p.weighted_score.dropna()
    axes[0].hist(scores,bins=np.arange(0,106,5),color='#2878B5'); axes[0].axvline(70,color='#B33333',ls='--',label='Pass threshold: 70')
    axes[0].set(xlabel='0.4 x A1 + 0.6 x A2',ylabel='Enrolments',title=f'Weighted scores: n={len(scores)}, unknown={int(p.weighted_score.isna().sum())}'); axes[0].legend()
    o=tables['outcome_by_timing'].set_index('timing_pattern').reindex(PATTERNS)
    axes[1].barh(PATTERNS,o.pass_rate_known*100,color='#438A69'); axes[1].set(xlim=(0,110),xlabel='Pass rate among known outcomes (%)',title='Pass rate by submission pattern')
    for i,row in enumerate(o.itertuples()): axes[1].text(2,i,f'{row.passes}/{row.known_outcomes}' if row.known_outcomes else 'No known outcomes',va='center')
    fig.suptitle(course); figures['05_course_outcomes'] = fig

    fig, axes = plt.subplots(1,2, figsize=(12,4.8), layout='constrained')
    for i,a in enumerate(['A1','A2']):
        vals=e.loc[e.assessment.eq(a),'grading_days'].dropna()
        if len(vals): axes[0].boxplot([vals],positions=[i],widths=.5)
    axes[0].set(xticks=[0,1],xticklabels=['A1','A2'],ylabel='Days from recorded submission to grading',title='Grading wait (not confirmed feedback release)')
    vals=p.feedback_interval_days.dropna()
    axes[1].hist(vals,bins=20,color='#D9792B'); axes[1].axvline(0,color='black',ls='--')
    axes[1].set(xlabel='Days from A1 grading to A2 submission',ylabel='Paired records',title=f'A1 grading before A2 submission: {int(vals.ge(0).sum())}/{len(vals)}\nPositive = grading occurred first')
    fig.suptitle(course); figures['06_grading_time'] = fig
    return figures


def run_analysis(input_path=DEFAULT_INPUT, output_dir=None, as_of=None, timezone='Australia/Melbourne'):
    d, meta = load_assignment_data(input_path, as_of, timezone)
    d.attrs['as_of'] = pd.Timestamp(meta['as_of_utc'])
    pairs = build_student_pairs(d)
    output = Path(output_dir) if output_dir else BASE/'outputs'/'assignment_analysis'
    output.mkdir(parents=True, exist_ok=True)
    combined = output/'combined'
    combined.mkdir(exist_ok=True)
    (combined/'analysis_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    audit=d.groupby(['course_name','course_canvas_id','assessment','assignment_id','assignment_name'],dropna=False).agg(
        records=('assignment_id','size'),due_min=('due_at','min'),due_max=('due_at','max'),
        submitted=('submitted','sum'),eligible=('due_eligible','sum')).reset_index()
    audit.to_csv(combined/'assignment_deadline_audit.csv',index=False)
    quality=d[KEY+['assessment','assignment_id']].copy()
    quality['missing_deadline']=d.due_at.isna()
    quality['score_outside_range']=(d.score<0)|(d.score>d.points_possible)
    quality['score_without_grading_time']=d.score.notna() & d.graded_at.isna()
    quality['submission_status_disagrees']=d.submitted_at.notna() & d.submission_status.eq('unsubmitted')
    quality['lead_over_60_days']=d.lead_days.abs()>60
    quality.loc[quality.iloc[:,5:].any(axis=1)].to_csv(combined/'data_quality.csv',index=False)
    summaries=[]
    for course,g in d.groupby('course_name',sort=True):
        p=pairs[pairs.course_name.eq(course)]
        tables,summary=summarize_course(g,p)
        summaries.append(summary)
        folder=output/('treaty' if course == TREATY else 'pbs')
        folder.mkdir(exist_ok=True)
        g.to_csv(folder/'assignment_records.csv',index=False)
        p.to_csv(folder/'student_assignment_pairs.csv',index=False)
        for name,table in tables.items(): table.to_csv(folder/(name+'.csv'),index=False)
        for name,fig in plot_course(g,p,tables).items():
            fig.savefig(folder/(name+'.png'),dpi=160,bbox_inches='tight'); plt.close(fig)
    result=pd.DataFrame(summaries)
    result.to_csv(combined/'course_summary.csv',index=False)
    # Keep existing overall outputs, and add independently recalculated Treaty terms.
    if TREATY in set(d.course_name):
        options = get_term_options(d, TREATY)
        (output/'treaty'/'treaty_term_options.json').write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding='utf-8')
        term_summaries = []
        for option in options[1:]:
            view = analyze_selection(d, TREATY, option['value'])
            term_summaries.append(view['summary'])
            folder = output/'treaty'/'terms'/re.sub(r'[^a-zA-Z0-9_-]', '_', option['value'])
            folder.mkdir(parents=True, exist_ok=True)
            for name, table in view['tables'].items():
                table.to_csv(folder/(name+'.csv'), index=False)
            view['pairs'].to_csv(folder/'student_assignment_pairs.csv', index=False)
            (folder/'notices.json').write_text(json.dumps(view['notices'], ensure_ascii=False, indent=2), encoding='utf-8')
            for name, fig in view['figures'].items():
                fig.savefig(folder/(name+'.png'), dpi=160, bbox_inches='tight'); plt.close(fig)
        pd.DataFrame(term_summaries).to_csv(output/'treaty'/'treaty_term_summary.csv', index=False)
    lines=['# Assignment analysis','',f"Observation cutoff: {meta['as_of_local']}",
        f"Cutoff source: {meta['cutoff_source']}",'',
        'Only positive-point A1/A2 records are selected. A1 weight = 40%, A2 = 60%; pass >= 70.',
        'Completion/timing summaries require the deadline to have passed. Pair summaries require both deadlines to have passed.',
        'A missing score stays unknown. Pass-rate denominator is known course outcomes, not all enrolled students.',
        'Rates in CSV files are fractions (0 to 1). Positive lead time means early; positive change means A2 was earlier.',
        'Cumulative submission curves retain eligible unsubmitted students in their denominator.',
        'Each course has the same six figures and summary tables. Repeated enrolments remain separate observations.',
        'Treaty term outputs are in treaty/terms, using full course codes including PAR. Course outputs are in pbs and treaty; cross-course summaries and audits are in combined.',
        'Python API: get_term_options(data, course); analyze_selection(data, course, term=None). See ASSIGNMENT_API.md for integration.',
        'No significance tests are reported: correlations are descriptive and observations may be dependent.','']
    for s in summaries:
        lines += [f"## {s['course']}",f"Eligible paired enrolments: {s['eligible_paired_enrolments']}; both submitted: {s['both_submitted']}.",
            f"Known outcomes: {s['known_outcomes']}; unknown: {s['unknown_outcomes']}; pass rate among known: {s['pass_rate_known']:.1%}.",
            f"Not-yet-due assignment records excluded from headline analysis: {s['not_yet_due_records']}.",'']
    lines += ['## Interpretation and data checks']+['- '+w for w in meta['warnings']]
    lines += ['', 'Inspect assignment_deadline_audit.csv and data_quality.csv before interpreting very early or late submissions.',
              'Repeated runs overwrite files with the same names in the selected output directory. Source data are never modified.']
    (combined/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    return result, output


def main():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input',type=Path,default=DEFAULT_INPUT)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--as-of',help='Verified observation/export date or timestamp; date includes entire local day')
    parser.add_argument('--timezone',default='Australia/Melbourne')
    args=parser.parse_args()
    summary,output=run_analysis(args.input,args.output_dir,args.as_of,args.timezone)
    print(summary.to_string(index=False)); print(f'\nSaved analysis to: {output.resolve()}')


if __name__=='__main__':
    main()
