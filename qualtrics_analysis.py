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

def load_survey_data(autism_path: str, treaty_path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    读取两份 Qualtrics 导出的 CSV，并各自打上 Course 标签。

    Qualtrics 导出有 3 行表头：
        第 1 行 = 列代码 (Q1_1, Q2, ...)   <- 保留作为列名
        第 2 行 = 完整题目文本             <- 跳过
        第 3 行 = JSON import IDs          <- 跳过
    """
    autism_df = pd.read_csv(autism_path, skiprows=[1, 2])
    treaty_df = pd.read_csv(treaty_path, skiprows=[1, 2])

    autism_df["Course"] = COURSES[0]
    treaty_df["Course"] = COURSES[1]

    return autism_df, treaty_df


# --------------------------------------------------------------------------
# RQ2: 长表整理（宽表 -> 长表，供后续统计/画图使用）
# --------------------------------------------------------------------------

def _to_long(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in STATEMENTS if c in df.columns]
    long = df.melt(id_vars=["Course"], value_vars=keep, var_name="Code", value_name="Response")
    long = long.dropna(subset=["Response"])
    long["Dimension"] = long["Code"].map(lambda c: STATEMENTS[c][0])
    long["Statement"] = long["Code"].map(lambda c: STATEMENTS[c][1])
    long["Score"] = long["Response"].map(LIKERT_MAP)
    return long


def build_long_format(autism_df: pd.DataFrame, treaty_df: pd.DataFrame) -> pd.DataFrame:
    """把两门课的宽表 Likert 数据合并成一张长表（Course / Dimension / Statement / Score）。"""
    return pd.concat([_to_long(autism_df), _to_long(treaty_df)], ignore_index=True)


# --------------------------------------------------------------------------
# RQ3: 汇总统计 — 主题均分 & NPS
# --------------------------------------------------------------------------

def get_theme_summary(long_df: pd.DataFrame) -> pd.DataFrame:
    """各课程在四个主题（Engagement / Learning experience / Impact / Assessment）上的平均得分（1-5）。"""
    dim_means = (
        long_df.groupby(["Course", "Dimension"])["Score"]
        .mean()
        .unstack("Dimension")[DIMENSIONS]
    )
    return dim_means.round(2)


def _nps_stats(df: pd.DataFrame) -> pd.Series:
    s = df["Q2"].dropna()
    n = len(s)
    promoters = (s >= 9).sum() / n * 100
    passives = ((s >= 7) & (s <= 8)).sum() / n * 100
    detractors = (s <= 6).sum() / n * 100
    return pd.Series({
        "n": n,
        "Promoters %": promoters,
        "Passives %": passives,
        "Detractors %": detractors,
        "NPS": promoters - detractors,
    })


def get_nps_summary(autism_df: pd.DataFrame, treaty_df: pd.DataFrame) -> pd.DataFrame:
    """各课程的 NPS（Net Promoter Score）分解统计。"""
    nps_table = pd.DataFrame(
        {course: _nps_stats(df) for course, df in zip(COURSES, [autism_df, treaty_df])}
    ).T
    return nps_table.round(1)


# --------------------------------------------------------------------------
# RQ4: 可视化 1 — 各主题平均分对比（分组柱状图）
# --------------------------------------------------------------------------

def plot_theme_agreement(long_df: pd.DataFrame) -> Figure:
    """两门课在四个主题上的平均得分，分组柱状图。"""
    _apply_chart_style()
    dim_means = get_theme_summary(long_df)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(DIMENSIONS))
    width = 0.35

    for i, course in enumerate(COURSES):
        vals = dim_means.loc[course].values
        offset = (i - 0.5) * width
        bars = ax.bar(x + offset, vals, width=width, color=COURSE_COLORS[course], label=course,
                       edgecolor="#fcfcfb", linewidth=1)
        for rect, v in zip(bars, vals):
            ax.text(rect.get_x() + rect.get_width() / 2, v + 0.05, f"{v:.2f}",
                     ha="center", va="bottom", fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels(DIMENSIONS)
    ax.set_ylim(0, 5.6)
    ax.set_ylabel("Mean agreement (1=Strongly disagree, 5=Strongly agree)")
    ax.set_title("Average agreement by theme, per MicroCert")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# RQ5: 可视化 2 — 响应分布（发散条形图，两门课在同一张图里对比）
# --------------------------------------------------------------------------

def plot_response_distribution(long_df: pd.DataFrame) -> Figure:
    """
    每个主题 x 每门课一行的发散条形图：
    不同意在左侧，同意在右侧，"中立"从中间对半分开。
    """
    _apply_chart_style()

    counts = long_df.groupby(["Course", "Dimension", "Response"]).size().unstack("Response", fill_value=0)
    counts = counts.reindex(columns=LIKERT_ORDER, fill_value=0)
    pct = counts.div(counts.sum(axis=1), axis=0) * 100

    rows = []
    y = 0
    group_gap = 0.7
    for dim in reversed(DIMENSIONS):
        for course in COURSES:
            rows.append((dim, course, y))
            y += 1
        y += group_gap

    fig, ax = plt.subplots(figsize=(10, 5.5))

    for dim, course, ypos in rows:
        row = pct.loc[(course, dim)]
        sd_r, sld_r = round(row["Strongly disagree"]), round(row["Slightly disagree"])
        sla_r, sa_r = round(row["Slightly agree"]), round(row["Strongly agree"])
        neutral_half = row["Neither agree nor disagree"] / 2

        agree_label = sla_r + sa_r
        disagree_label = sd_r + sld_r
        disagree_components = sum(1 for v in (row["Strongly disagree"], row["Slightly disagree"]) if v > 0)
        label_y_offset = {"Strongly disagree": 0.18, "Slightly disagree": -0.18} if disagree_components >= 2 else {}

        cur = -(row["Strongly disagree"] + row["Slightly disagree"] + neutral_half)
        segs = [
            ("Strongly disagree", row["Strongly disagree"], sd_r, "always"),
            ("Slightly disagree", row["Slightly disagree"], sld_r, "always"),
            ("Neither agree nor disagree", neutral_half, None, "never"),
            ("Neither agree nor disagree", neutral_half, None, "never"),
            ("Slightly agree", row["Slightly agree"], sla_r, "threshold"),
            ("Strongly agree", row["Strongly agree"], sa_r, "threshold"),
        ]
        for label, w, w_r, rule in segs:
            if w > 0:
                ax.barh(ypos, w, left=cur, height=0.75, color=LIKERT_COLORS[label],
                        edgecolor="#fcfcfb", linewidth=1)
                show = (rule == "always") or (rule == "threshold" and w >= AGREE_LABEL_THRESHOLD)
                if show:
                    text_color = LIKERT_TEXT_COLOR[label] if w >= 4 else "#0b0b0b"
                    ax.text(cur + w / 2, ypos + label_y_offset.get(label, 0), f"{w_r:.0f}%",
                            ha="center", va="center", fontsize=8, color=text_color, clip_on=False)
            cur += w

        right_end = row["Slightly agree"] + row["Strongly agree"] + neutral_half
        left_end = -(row["Strongly disagree"] + row["Slightly disagree"] + neutral_half)
        ax.text(right_end + 2, ypos, f"{agree_label:.0f}% agree", va="center", ha="left",
                fontsize=8.5, color="#0b0b0b", clip_on=False)
        if disagree_components >= 2:
            ax.text(left_end - 2, ypos, f"{disagree_label:.0f}% disagree", va="center", ha="right",
                    fontsize=8.5, color="#0b0b0b", clip_on=False)

    ax.axvline(0, color="#898781", linewidth=1)
    ax.set_yticks([r[2] for r in rows])
    ax.set_yticklabels([COURSE_SHORT[r[1]] for r in rows])

    theme_rows: dict[str, list[float]] = {}
    for dim, course, ypos in rows:
        theme_rows.setdefault(dim, []).append(ypos)
    for dim, ys in theme_rows.items():
        ax.text(-0.14, sum(ys) / len(ys), dim, transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=10.5, fontweight="bold", color="#0b0b0b")

    ax.set_xlim(-40, 112)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, pos: f"{abs(v):.0f}%"))
    ax.set_ylim(-0.6, y - group_gap + 0.6)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", visible=False)
    ax.set_title("Response distribution by theme (% of responses)", fontsize=12, pad=14)

    handles = [plt.Rectangle((0, 0), 1, 1, color=LIKERT_COLORS[l]) for l in LIKERT_ORDER]
    ax.legend(handles, LIKERT_ORDER, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.08))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# RQ6: 可视化 3 — Net Promoter Score 分解
# --------------------------------------------------------------------------

def plot_nps_breakdown(autism_df: pd.DataFrame, treaty_df: pd.DataFrame) -> Figure:
    """Promoters / Passives / Detractors 占比，以及每门课的 NPS 值。"""
    _apply_chart_style()
    nps_table = get_nps_summary(autism_df, treaty_df)

    fig, ax = plt.subplots(figsize=(7, 3.8))
    y = np.arange(len(COURSES))
    for i, course in enumerate(COURSES):
        row = nps_table.loc[course]
        left = 0
        for label in ["Detractors", "Passives", "Promoters"]:
            val = row[f"{label} %"]
            ax.barh(i, val, left=left, color=STATUS_COLORS[label], height=0.5, edgecolor="#fcfcfb", linewidth=1)
            if val > 5:
                text_color = "white" if label != "Passives" else "#0b0b0b"
                ax.text(left + val / 2, i, f"{val:.0f}%", ha="center", va="center", fontsize=9, color=text_color)
            left += val
        ax.text(103, i, f"NPS {row['NPS']:+.0f}  (n={int(row['n'])})", va="center", ha="left", fontsize=9.5)

    ax.set_yticks(y)
    ax.set_yticklabels(COURSES)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of respondents (%)")
    ax.set_title("Net Promoter Score breakdown")
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.grid(axis="y", visible=False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=STATUS_COLORS[l]) for l in ["Detractors", "Passives", "Promoters"]]
    ax.legend(handles, ["Detractors (0-6)", "Passives (7-8)", "Promoters (9-10)"], loc="upper center",
              bbox_to_anchor=(0.5, -0.18), ncol=3, frameon=False)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# RQ7: 开放题文本
# --------------------------------------------------------------------------

def get_qualitative_responses(
    autism_df: pd.DataFrame, treaty_df: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """
    返回 {题目代码: 合并后的两课回答 DataFrame}，题目见 TEXT_QUESTIONS：
        Q6.0 -> How they'll apply it
        Q7.0 -> Best aspects
        Q8.0 -> Areas to improve
    """
    result = {}
    for code in TEXT_QUESTIONS:
        combined = pd.concat([
            autism_df[["Course", code]].rename(columns={code: "Response"}),
            treaty_df[["Course", code]].rename(columns={code: "Response"}),
        ]).dropna(subset=["Response"]).reset_index(drop=True)
        result[code] = combined
    return result


# --------------------------------------------------------------------------
# RQ8: 词云
# --------------------------------------------------------------------------

def plot_wordclouds(autism_df: pd.DataFrame, treaty_df: pd.DataFrame) -> Figure:
    """
    对 TEXT_QUESTIONS 里的每个开放题，各课程画一张词云。
    蓝色 = Autism Affirming Practice，橙色 = Understanding Treaty。
    需要 `pip install wordcloud`。
    """
    from wordcloud import WordCloud, STOPWORDS
    from matplotlib.colors import LinearSegmentedColormap

    _apply_chart_style()

    extra_stopwords = {"nil", "na", "n/a", "none", "will", "course", "etc"}
    stop = STOPWORDS.union(extra_stopwords)

    def course_colormap(hex_color: str) -> LinearSegmentedColormap:
        return LinearSegmentedColormap.from_list("course", ["#c9c9c9", hex_color])

    fig, axes = plt.subplots(len(TEXT_QUESTIONS), len(COURSES), figsize=(11, 3.75 * len(TEXT_QUESTIONS)))
    for r, (code, label) in enumerate(TEXT_QUESTIONS.items()):
        for c, course in enumerate(COURSES):
            df = autism_df if course == COURSES[0] else treaty_df
            text = " ".join(df[code].dropna().astype(str).tolist())
            ax = axes[r, c]
            if not text.strip():
                ax.axis("off")
                continue
            wc = WordCloud(
                width=800, height=500, background_color="#fcfcfb",
                colormap=course_colormap(COURSE_COLORS[course]),
                stopwords=stop, collocations=False, prefer_horizontal=0.95,
                max_words=60, random_state=42,
            ).generate(text)
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            ax.set_title(f"{course}\n{label} ({code})", fontsize=10)

    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# CLI 入口（可直接运行）
# --------------------------------------------------------------------------


def _find_csv_matches(keywords: list[str]) -> list[str]:
    """在项目目录和 Datasets 目录中寻找可能的 CSV 文件。优先按关键词，其次按所有 CSV。"""
    search_roots = [".", "Datasets"]
    expanded = []
    for root in search_roots:
        if not Path(root).exists():
            continue
        for kw in keywords:
            expanded.extend(glob.glob(f"{root}/**/*{kw}*.csv", recursive=True))
            expanded.extend(glob.glob(f"{root}/**/*{kw}*.CSV", recursive=True))
        expanded.extend(glob.glob(f"{root}/**/*.csv", recursive=True))
        expanded.extend(glob.glob(f"{root}/**/*.CSV", recursive=True))
    unique = []
    for path in expanded:
        if path not in unique:
            unique.append(path)
    return sorted(unique)


def _is_qualtrics_csv(path: str) -> bool:
    """Heuristic check: Qualtrics exports have survey question columns like Q1_1, Q2, Q6.0."""
    try:
        df = pd.read_csv(path, nrows=3)
    except Exception:
        return False
    cols = {str(c) for c in df.columns}
    return any(col in cols for col in ["Q1_1", "Q2", "Q6.0", "Q7.0", "Q8.0", "Q3.0_1", "Q4.0_1"]) or any(
        col.startswith("Q") for col in cols
    )


def _resolve_input_files(autism_path: str | None, treaty_path: str | None) -> tuple[str, str]:
    """Resolve input CSV paths, including automatic discovery when paths aren't supplied."""
    if autism_path and treaty_path:
        return autism_path, treaty_path

    all_csvs = _find_csv_matches(["autism", "Autism", "autism affirming", "Autism Affirming", "treaty", "Treaty", "understanding treaty", "Understanding Treaty"])
    qualtrics_candidates = [p for p in all_csvs if _is_qualtrics_csv(p)]

    autism_candidates = [p for p in qualtrics_candidates if any(k.lower() in p.lower() for k in ["autism", "affirming"]) or "0AUTI" in p]
    treaty_candidates = [p for p in qualtrics_candidates if any(k.lower() in p.lower() for k in ["treaty", "understanding"]) or "0UNDE" in p]

    if not autism_path and autism_candidates:
        autism_path = autism_candidates[0]
    if not treaty_path and treaty_candidates:
        treaty_path = treaty_candidates[0]

    if not autism_path or not treaty_path:
        raise FileNotFoundError(
            "Could not find both Qualtrics CSV inputs. Please provide --autism and --treaty, "
            "or place the exported Qualtrics CSV files in the project folder or in the Datasets folder."
        )
    return autism_path, treaty_path


def _save_fig(fig: Figure, output_path: str) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200, bbox_inches="tight")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualtrics survey analysis for the Treaty Series MicroCert programs.")
    parser.add_argument("--autism", type=str, default=None, help="Path to the Autism Affirming Practice CSV export.")
    parser.add_argument("--treaty", type=str, default=None, help="Path to the Understanding Treaty CSV export.")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Directory to save charts and summaries.")
    parser.add_argument("--show-plots", action="store_true", help="Open generated plots in a window after saving them.")
    args = parser.parse_args(argv)

    try:
        autism_input, treaty_input = _resolve_input_files(args.autism, args.treaty)
    except FileNotFoundError as exc:
        print(f"Input error: {exc}")
        return 1

    autism_df, treaty_df = load_survey_data(autism_input, treaty_input)
    long_df = build_long_format(autism_df, treaty_df)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    theme_summary = get_theme_summary(long_df)
    nps_summary = get_nps_summary(autism_df, treaty_df)
    print("Theme summary:\n", theme_summary)
    print("\nNPS summary:\n", nps_summary)

    chart_paths = {
        "theme_agreement": _save_fig(plot_theme_agreement(long_df), str(output_dir / "theme_agreement.png")),
        "response_distribution": _save_fig(plot_response_distribution(long_df), str(output_dir / "response_distribution.png")),
        "nps_breakdown": _save_fig(plot_nps_breakdown(autism_df, treaty_df), str(output_dir / "nps_breakdown.png")),
    }

    qualitative = get_qualitative_responses(autism_df, treaty_df)
    for code, df in qualitative.items():
        out_path = output_dir / f"qualitative_{code}.csv"
        df.to_csv(out_path, index=False)
        print(f"\nSaved qualitative responses for {code} to {out_path}")

    wordcloud_fig = plot_wordclouds(autism_df, treaty_df)
    chart_paths["wordclouds"] = _save_fig(wordcloud_fig, str(output_dir / "wordclouds.png"))

    print("\nSaved charts:")
    for name, path in chart_paths.items():
        print(f"  - {name}: {path}")

    if args.show_plots:
        plt.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
