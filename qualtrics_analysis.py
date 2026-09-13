"""
qualtrics_analysis.py

Treaty Series MicroCert 学员满意度分析模块（从 Qualtrics.ipynb 重构而来）。

设计原则（对应你截图里的思路）：
    每一个研究问题（RQ）对应一个函数，函数只接收数据（DataFrame / 路径），
    返回一个结果（DataFrame 或 matplotlib Figure），不在函数内部 print/show。
    这样 Streamlit 前端可以直接：

        from qualtrics_analysis import load_survey_data, build_long_format, ...
        autism_df, treaty_df = load_survey_data(path1, path2)
        long_df = build_long_format(autism_df, treaty_df)
        st.dataframe(get_theme_summary(long_df))
        st.pyplot(plot_theme_agreement(long_df))

RQ 对照表：
    RQ1  数据加载           -> load_survey_data
    RQ2  长表整理           -> build_long_format
    RQ3  主题均分 / NPS 统计 -> get_theme_summary / get_nps_summary
    RQ4  主题均分柱状图      -> plot_theme_agreement
    RQ5  分布对比图（发散条）-> plot_response_distribution
    RQ6  NPS 分解图         -> plot_nps_breakdown
    RQ7  开放题文本         -> get_qualitative_responses
    RQ8  词云               -> plot_wordclouds
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.figure import Figure

# --------------------------------------------------------------------------
# 常量（前端如果要做筛选/下拉框，也可以直接从这里 import）
# --------------------------------------------------------------------------

COURSES = ["Autism Affirming Practice", "Understanding Treaty"]
COURSE_SHORT = {"Autism Affirming Practice": "Autism", "Understanding Treaty": "Treaty"}
COURSE_COLORS = {"Autism Affirming Practice": "#2a78d6", "Understanding Treaty": "#eb6834"}

# 5 分 Likert 量表 -> 数值分
LIKERT_ORDER = [
    "Strongly disagree",
    "Slightly disagree",
    "Neither agree nor disagree",
    "Slightly agree",
    "Strongly agree",
]
LIKERT_MAP = {label: score for score, label in enumerate(LIKERT_ORDER, start=1)}
LIKERT_COLORS = {
    "Strongly disagree": "#e34948",
    "Slightly disagree": "#f2b7b6",
    "Neither agree nor disagree": "#c3c2b7",
    "Slightly agree": "#9ec5f4",
    "Strongly agree": "#2a78d6",
}
LIKERT_TEXT_COLOR = {
    "Strongly disagree": "white",
    "Slightly disagree": "#0b0b0b",
    "Neither agree nor disagree": "#0b0b0b",
    "Slightly agree": "#0b0b0b",
    "Strongly agree": "white",
}

# 题目代码 -> (主题 Dimension, 简短标签 Statement)
STATEMENTS = {
    "Q1_1": ("Engagement", "Intellectually engaging"),
    "Q1_2": ("Engagement", "Clear expectations"),
    "Q1_3": ("Engagement", "Informed by research/practice"),
    "Q1_4": ("Engagement", "Helpful learning resources"),
    "Q1_5": ("Engagement", "Good learning experience overall"),
    "Q3.0_1": ("Learning experience", "Valuable feedback"),
    "Q3.0_2": ("Learning experience", "Peer interaction"),
    "Q3.0_3": ("Learning experience", "Manageable workload"),
    "Q3.0_4": ("Learning experience", "Industry representation"),
    "Q4.0_1": ("Impact", "Learnt new ideas/skills"),
    "Q4.0_2": ("Impact", "Applied knowledge to practice"),
    "Q4.0_3": ("Impact", "Challenged my thinking"),
    "Q4.0_4": ("Impact", "Developed workplace skills"),
    "Q4.0_5": ("Impact", "Improved understanding of concepts"),
    "Q5.0_1": ("Assessment", "Demonstrated learning"),
    "Q5.0_2": ("Assessment", "Increased understanding"),
    "Q5.0_3": ("Assessment", "Applicable to current workplace"),
    "Q5.0_4": ("Assessment", "Applicable to future workplace"),
    "Q5.0_5": ("Assessment", "Clear grading criteria"),
}
DIMENSIONS = ["Engagement", "Learning experience", "Impact", "Assessment"]

TEXT_QUESTIONS = {
    "Q6.0": "How they'll apply it",
    "Q7.0": "Best aspects",
    "Q8.0": "Areas to improve",
}

STATUS_COLORS = {"Promoters": "#0ca30c", "Passives": "#fab219", "Detractors": "#d03b3b"}

AGREE_LABEL_THRESHOLD = 8  # 只在 >= 这个百分比的 agree 分段上打标签


def _apply_chart_style() -> None:
    """统一的 matplotlib 主题（原 notebook 里的 rcParams.update）。"""
    plt.rcParams.update({
        "figure.facecolor": "#fcfcfb",
        "axes.facecolor": "#fcfcfb",
        "axes.edgecolor": "#c3c2b7",
        "axes.labelcolor": "#0b0b0b",
        "text.color": "#0b0b0b",
        "xtick.color": "#52514e",
        "ytick.color": "#52514e",
        "axes.grid": True,
        "grid.color": "#e1e0d9",
        "grid.linewidth": 0.8,
        "font.size": 10,
    })


# --------------------------------------------------------------------------
# RQ1: 数据加载
# --------------------------------------------------------------------------

def load_survey_data(autism_path: str, treaty_path: str):
    """Read raw three-header-row Qualtrics CSV exports; input order is fixed."""
    frames = []
    for path, course in zip([autism_path, treaty_path], COURSES):
        frame = pd.read_csv(path, skiprows=[1, 2])
        frame['Course'] = course
        frames.append(frame)
    return tuple(frames)


def get_course_options():
    return [{'value': None, 'label': '整体 / All courses'}] + [
        {'value': course, 'label': course} for course in COURSES]


def _validate_frames(autism_df, treaty_df, course=None):
    if course is not None and course not in COURSES:
        raise ValueError(f'Unknown course: {course}')
    frames, notices = [], []
    for source, name in zip([autism_df, treaty_df], COURSES):
        if course is not None and course != name:
            continue
        df = source.copy()
        df['Course'] = name
        if df.empty:
            notices.append(f'{name}: 没有问卷记录。')
        missing = [c for c in [*STATEMENTS, 'Q2', *TEXT_QUESTIONS] if c not in df]
        if missing:
            notices.append(f"{name}: 缺少字段 {', '.join(missing)}，对应结果按缺失处理。")
        for code in STATEMENTS:
            s = df[code] if code in df else pd.Series(pd.NA, index=df.index, dtype='string')
            s = s.astype('string').str.strip().replace('', pd.NA)
            bad = s.notna() & ~s.isin(LIKERT_ORDER)
            if bad.any():
                notices.append(f'{name} / {code}: {int(bad.sum())} 条无法识别的 Likert 回答已排除。')
            df[code] = s.where(s.isin(LIKERT_ORDER))
        raw = df['Q2'] if 'Q2' in df else pd.Series(pd.NA, index=df.index)
        raw = raw.astype('string').str.strip().replace('', pd.NA)
        numeric = pd.to_numeric(raw, errors='coerce')
        valid = numeric.between(0, 10) & numeric.mod(1).eq(0)
        invalid = raw.notna() & ~valid.fillna(False)
        if invalid.any():
            notices.append(f'{name} / Q2: {int(invalid.sum())} 条非 0–10 整数的回答已排除。')
        df['Q2'] = numeric.where(valid).astype(float)
        for code in TEXT_QUESTIONS:
            raw = df[code] if code in df else pd.Series(pd.NA, index=df.index, dtype='string')
            df[code] = raw.astype('string').str.strip().replace('', pd.NA)
        frames.append(df)
    return frames, notices


def _to_long(df):
    long = df.melt(id_vars=['Course'], value_vars=list(STATEMENTS), var_name='Code', value_name='Response')
    long = long.dropna(subset=['Response']).copy()
    long['Dimension'] = long.Code.map(lambda c: STATEMENTS[c][0])
    long['Statement'] = long.Code.map(lambda c: STATEMENTS[c][1])
    long['Score'] = long.Response.map(LIKERT_MAP)
    return long


def build_long_format(autism_df, treaty_df):
    frames, _ = _validate_frames(autism_df, treaty_df)
    long = pd.concat([_to_long(df) for df in frames], ignore_index=True)
    long.attrs['courses'] = COURSES.copy()
    return long


def _courses(long_df):
    if 'selected_courses' in long_df.attrs:
        return long_df.attrs['selected_courses']
    present = long_df.Course.dropna().unique().tolist()
    return [c for c in COURSES if c in present] if present else long_df.attrs.get('courses', [])


def get_theme_summary(long_df):
    courses = _courses(long_df)
    if long_df.empty:
        return pd.DataFrame(index=pd.Index(courses, name='Course'), columns=DIMENSIONS, dtype=float)
    return long_df.groupby(['Course', 'Dimension']).Score.mean().unstack().reindex(
        index=courses, columns=DIMENSIONS).round(2)


def _nps_table(frames):
    rows = []
    for name, df in frames:
        s = df.Q2.dropna()
        n = len(s)
        pro = (s >= 9).mean()*100 if n else np.nan
        pas = s.between(7, 8).mean()*100 if n else np.nan
        det = (s <= 6).mean()*100 if n else np.nan
        rows.append({'Course': name, 'n': n, 'Promoters %': pro, 'Passives %': pas,
                     'Detractors %': det, 'NPS': pro-det})
    return pd.DataFrame(rows).set_index('Course').round(1)


def get_nps_summary(autism_df, treaty_df):
    frames, _ = _validate_frames(autism_df, treaty_df)
    return _nps_table(list(zip(COURSES, frames)))


def _empty(ax, message='No valid responses'):
    ax.text(.5, .5, message, ha='center', va='center', transform=ax.transAxes)
    ax.set_axis_off()


def plot_theme_agreement(long_df):
    _apply_chart_style()
    table = get_theme_summary(long_df)
    fig, ax = plt.subplots(figsize=(9, 4.5), layout='constrained')
    if table.empty or table.isna().all().all():
        _empty(ax); return fig
    width = .75 / len(table)
    for i, (course, row) in enumerate(table.iterrows()):
        positions = np.arange(len(DIMENSIONS)) + (i-(len(table)-1)/2)*width
        ax.bar(positions, row, width=width, color=COURSE_COLORS[course], label=course)
        for x, value in zip(positions, row):
            ax.text(x, value+.05 if pd.notna(value) else .1, f'{value:.2f}' if pd.notna(value) else 'N/A', ha='center', fontsize=8)
    ax.set(xticks=np.arange(4), xticklabels=DIMENSIONS, ylim=(0,5.6), ylabel='Mean agreement (1–5)', title='Average agreement by theme')
    ax.legend(loc='lower right'); return fig


def _response_table(long_df):
    index = pd.MultiIndex.from_product([_courses(long_df), DIMENSIONS], names=['Course','Dimension'])
    if long_df.empty:
        counts = pd.DataFrame(0, index=index, columns=LIKERT_ORDER)
    else:
        counts = long_df.groupby(['Course','Dimension','Response']).size().unstack(fill_value=0).reindex(index=index, columns=LIKERT_ORDER, fill_value=0)
    return counts.div(counts.sum(axis=1).replace(0, np.nan), axis=0)*100


def plot_response_distribution(long_df):
    _apply_chart_style()
    pct = _response_table(long_df)
    fig, ax = plt.subplots(figsize=(11, max(3.5, len(pct)*.65)), layout='constrained')
    if pct.empty:
        _empty(ax); return fig
    for y, (_, row) in enumerate(pct.iterrows()):
        if row.isna().all():
            ax.text(2,y,'No valid responses', va='center'); continue
        left = -(row.iloc[0]+row.iloc[1]+row.iloc[2]/2)
        for label in LIKERT_ORDER:
            w = row[label]
            ax.barh(y,w,left=left,color=LIKERT_COLORS[label],height=.7)
            if w >= 8: ax.text(left+w/2,y,f'{w:.0f}%',ha='center',va='center',fontsize=8)
            left += w
    ax.axvline(0,color='gray')
    ax.set(yticks=np.arange(len(pct)), yticklabels=[f'{d} — {COURSE_SHORT[c]}' for c,d in pct.index],
           xlim=(-105,105),title='Response distribution (% of valid item responses)')
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v,p:f'{abs(v):.0f}%'))
    ax.legend([plt.Rectangle((0,0),1,1,color=LIKERT_COLORS[l]) for l in LIKERT_ORDER],LIKERT_ORDER,
              loc='upper center',bbox_to_anchor=(.5,-.08),ncol=3,frameon=False)
    return fig


def _plot_nps(table):
    _apply_chart_style()
    fig, ax = plt.subplots(figsize=(9,3.8),layout='constrained')
    for y, (course,row) in enumerate(table.iterrows()):
        if row['n']==0:
            ax.text(2,y,'No valid NPS responses',va='center'); continue
        left=0
        for label in ['Detractors','Passives','Promoters']:
            value=row[label+' %']
            ax.barh(y,value,left=left,color=STATUS_COLORS[label],height=.5)
            if value>5: ax.text(left+value/2,y,f'{value:.0f}%',ha='center',va='center')
            left+=value
        ax.text(102,y,f"NPS {row['NPS']:+.1f}; n={int(row['n'])}",va='center')
    ax.set(yticks=np.arange(len(table)),yticklabels=table.index,xlim=(0,135),xticks=[0,25,50,75,100],xlabel='Respondents (%)',title='Net Promoter Score breakdown')
    ax.legend([plt.Rectangle((0,0),1,1,color=STATUS_COLORS[l]) for l in ['Detractors','Passives','Promoters']],
              ['Detractors (0–6)','Passives (7–8)','Promoters (9–10)'],loc='upper center',bbox_to_anchor=(.5,-.18),ncol=3)
    return fig


def plot_nps_breakdown(autism_df, treaty_df):
    return _plot_nps(get_nps_summary(autism_df,treaty_df))


def _texts(frames):
    return {code:pd.concat([df[['Course',code]].rename(columns={code:'Response'}) for df in frames],ignore_index=True).dropna(subset=['Response']).reset_index(drop=True) for code in TEXT_QUESTIONS}


def get_qualitative_responses(autism_df,treaty_df):
    frames,_=_validate_frames(autism_df,treaty_df)
    return _texts(frames)


def _wordclouds(frames, names):
    from wordcloud import WordCloud, STOPWORDS
    _apply_chart_style()
    fig,axes=plt.subplots(3,len(frames),figsize=(5.5*len(frames),10),squeeze=False,layout='constrained')
    try:
        for r,(code,label) in enumerate(TEXT_QUESTIONS.items()):
            for c,(df,name) in enumerate(zip(frames,names)):
                ax=axes[r,c]
                wc=WordCloud(width=800,height=500,background_color='white',stopwords=STOPWORDS.union({'nil','na','n/a','none','will','course','etc'}),collocations=False,max_words=60,random_state=42)
                words=wc.process_text(' '.join(df[code].dropna().astype(str)))
                if words:
                    wc.generate_from_frequencies(words)
                    color=COURSE_COLORS[name]
                    wc.recolor(color_func=lambda *args, **kwargs: color)
                    ax.imshow(wc,interpolation='bilinear'); ax.axis('off')
                else: _empty(ax,'No usable words')
                ax.set_title(f'{name}\n{label} ({code})',fontsize=10)
        return fig
    except Exception:
        plt.close(fig)
        raise


def plot_wordclouds(autism_df,treaty_df):
    frames,_=_validate_frames(autism_df,treaty_df)
    return _wordclouds(frames,COURSES)


def analyze_survey(autism_df, treaty_df, course=None, include_figures=True, include_wordclouds=False):
    """Unified API. None = both courses; invalid course raises ValueError. Inputs untouched."""
    frames,notices=_validate_frames(autism_df,treaty_df,course)
    names=COURSES.copy() if course is None else [course]
    long=pd.concat([_to_long(df) for df in frames],ignore_index=True)
    long.attrs['courses']=names
    long.attrs['selected_courses']=names
    # Keep empty selected courses represented in summary and figures.
    theme=get_theme_summary(long).reindex(names)
    nps=_nps_table(list(zip(names,frames)))
    texts=_texts(frames)
    summary={'courses':names,'respondent_rows':dict(zip(names,[len(df) for df in frames])),
             'valid_likert_responses':len(long),'valid_nps_responses':int(nps.n.sum())}
    for name,df in zip(names,frames):
        if df[list(STATEMENTS)].notna().sum().sum()==0: notices.append(f'{name}: 没有有效 Likert 回答。')
        if df.Q2.notna().sum()==0: notices.append(f'{name}: 没有有效 NPS 回答。')
    tables={'theme_summary':theme,'nps_summary':nps,'response_distribution':_response_table(long),
            'theme_response_counts':long.groupby(['Course','Dimension']).size().reindex(pd.MultiIndex.from_product([names,DIMENSIONS],names=['Course','Dimension']),fill_value=0).rename('n').reset_index()}
    figures={}
    try:
        if include_figures:
            figures={'theme_agreement':plot_theme_agreement(long),'response_distribution':plot_response_distribution(long),'nps_breakdown':_plot_nps(nps)}
            if include_wordclouds:
                try: figures['wordclouds']=_wordclouds(frames,names)
                except ImportError: notices.append('未安装 wordcloud，已跳过词云；其他结果可用。')
    except Exception:
        for fig in figures.values(): plt.close(fig)
        raise
    return {'summary':summary,'tables':tables,'figures':figures,'notices':notices,'qualitative':texts,'long_data':long,
            'metadata':{'course':course,'likert_scale':[1,5],'percentage_scale':[0,100],
                        'limitations':['未自动筛选完成状态或去重。','主题均分以有效题目回答为单位，不是先按受访者平均。','未提供 term 筛选或 HTTP 服务。']}}


def _resolve_input_files(autism_path=None,treaty_path=None):
    root=Path(__file__).resolve().parent
    candidates=sorted((root/'Datasets').glob('*.csv'))
    def find(words):
        for p in candidates:
            if not any(w.lower() in p.name.lower() for w in words): continue
            if 'Q2' in pd.read_csv(p,nrows=0).columns: return str(p)
        raise FileNotFoundError('请使用 --autism 和 --treaty 指定原始 Qualtrics CSV。')
    return autism_path or find(['autism','0AUTI']),treaty_path or find(['treaty','0UNDE'])


def export_survey_result(result, output_dir, show_plots=False):
    """Write one selected view; close all figures after export."""
    import json
    output=Path(output_dir)
    output.mkdir(parents=True,exist_ok=True)
    try:
        for name,table in result['tables'].items(): table.to_csv(output/(name+'.csv'),index=name!='theme_response_counts')
        for code,table in result['qualitative'].items(): table.to_csv(output/f'qualitative_{code}.csv',index=False)
        for name,fig in result['figures'].items(): fig.savefig(output/(name+'.png'),dpi=180,bbox_inches='tight')
        (output/'analysis_metadata.json').write_text(json.dumps({k:result[k] for k in ['summary','notices','metadata']},ensure_ascii=False,indent=2),encoding='utf-8')
        if show_plots: plt.show()
    finally:
        for fig in result['figures'].values(): plt.close(fig)
    return output


def main(argv=None):
    parser=argparse.ArgumentParser(description='Qualtrics backend analysis')
    parser.add_argument('--autism'); parser.add_argument('--treaty')
    parser.add_argument('--course',choices=[*COURSES,'overall'],default=None,
                        help='Omit to export PBS, Treaty and overall; overall exports only the combined view.')
    parser.add_argument('--output-dir',default=str(Path(__file__).resolve().parent/'outputs'/'qualtrics_analysis'))
    parser.add_argument('--show-plots',action='store_true')
    args=parser.parse_args(argv)
    a,t=load_survey_data(*_resolve_input_files(args.autism,args.treaty))
    scopes=[(COURSES[0],'pbs'),(COURSES[1],'treaty'),(None,'combined')]
    if args.course is not None:
        selected=None if args.course=='overall' else args.course
        scopes=[(course,folder) for course,folder in scopes if course==selected]
    for course,folder in scopes:
        result=analyze_survey(a,t,course,include_wordclouds=True)
        output=export_survey_result(result,Path(args.output_dir)/folder,args.show_plots)
        print(f'Saved Qualtrics outputs: {output}')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
