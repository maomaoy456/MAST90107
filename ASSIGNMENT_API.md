# Assignment analysis：后端接口说明

本模块只提供 Python 数据分析接口及批量导出，不包含前端页面或 HTTP 服务。前端同学可以直接导入模块，或在自己的服务层封装为 HTTP 接口。

依赖：`pandas numpy matplotlib scipy openpyxl`，不需要 Streamlit。

## 调用顺序

```python
from assignment_analysis import (
    DEFAULT_INPUT, load_assignment_data, get_term_options, analyze_selection,
)

# as_of 可传已确认的导出日期；None 使用最新事件时间作为推定观察时点。
data, metadata = load_assignment_data(DEFAULT_INPUT, as_of=None)
courses = sorted(data['course_name'].unique().tolist())
course = 'Understanding Treaty'
options = get_term_options(data, course)
# options: [{'value': None, 'label': '整体 / All terms'}, ...]

# 整体：term=None；指定 term：使用 options 中的 value，不能用 label 代替。
result = analyze_selection(data, course, term=None, include_figures=False)
term_result = analyze_selection(
    data, course, term='0UNDE0001_2025_MAR_PAR_4', include_figures=True,
)
```

## 返回值

`load_assignment_data` 返回清洗后的 DataFrame 和 metadata 字典。metadata 包含观察时点、时区、原始/纳入/排除记录数和解释限制。缓存数据时应考虑源文件修改时间与观察日期。

`get_term_options` 返回按时间排序的 `value` / `label` 列表。Treaty 支持整体和 7 个完整开课代码；保留 PAR 区分，避免把不同截止日期的班级合并。PBS 仅提供整体选项。

`analyze_selection` 在筛选之后重新配对和计算，返回以下字典：

| 键 | 类型 | 内容 |
|---|---|---|
| records | pandas.DataFrame | 所选范围的正式 A1/A2 记录，含 due_eligible 等标记；包含尚未到期的记录供检查 |
| pairs | pandas.DataFrame | 同一次修读内的 A1/A2 配对，含 pair_eligible 标记 |
| summary | dict | 所选范围的样本量、完成情况、总分/通过率、term_id、term_label 等 |
| tables | dict[str, DataFrame] | assignment_summary、completion、outcomes、outcome_by_timing、associations |
| notices | list[str] | 当前所选范围的数据核查提示，例如距截止时间超过 60 天的记录 |
| figures | dict[str, matplotlib.figure.Figure] | 六组图；include_figures=False 时为空字典 |

图名依次为 `01_completion`、`02_submission_timing`、`03_paired_timing`、`04_timing_and_scores`、`05_course_outcomes`、`06_grading_time`。标题标明当前整体或 term 范围。无效课程或 term 抛出 `ValueError`，不会默默退回整体。

## 对前端展示重要的口径

- 仅纳入正满分的正式 A1/A2；完成统计要求已到期，配对统计要求两次均到期。
- 总分 = A1 × 40% + A2 × 60%，总分 ≥70 为通过。缺失成绩不填零，课程结果为 Unknown。
- `pass_rate_known` 分母仅为成绩完整者；务必同时展示 unknown_outcomes，不能当作全体通过率。
- 比例字段为 0～1，显示百分比时乘 100。学生数与修读记录数可能不同，整体不能简单相加 term 的去重学生数。
- `lead_days` 为截止时间减提交时间，正数表示提前。提交时间分布图使用其相反数，负数提前、正数迟交。
- `records` 和 `pairs` 保留未到期记录；页面汇总应使用 summary/tables，或先应用 due_eligible/pair_eligible。
- 空样本或不可计算的指标可能为 NaN，前端应显示“暂无数据”，不要显示为零。
- 原始截止日期不自动修改；notices 和 metadata 中的限制需要向使用者保留。

## 序列化与图形生命周期

返回的是 Python 对象，不是可直接发送的 JSON。DataFrame 可用下式转换，NaN 将转换为 null：

```python
import json
import pandas as pd

table_payload = json.loads(result['tables']['completion'].to_json(orient='records', date_format='iso'))
summary_payload = json.loads(pd.DataFrame([result['summary']]).to_json(orient='records'))[0]
```

若需要图片，调用方将 Figure 导出为 PNG 字节，使用完后关闭。部署多线程服务时，将绘图放入串行队列或独立进程，避免 Matplotlib 的共享状态并发问题。

```python
from io import BytesIO
import matplotlib.pyplot as plt

images = {}
try:
    for name, fig in term_result['figures'].items():
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=160, bbox_inches='tight')
        images[name] = buffer.getvalue()
finally:
    for fig in term_result['figures'].values():
        plt.close(fig)
```

命令行运行 `python assignment_analysis.py` 可批量导出两门课整体及 Treaty 各 term 的 CSV/PNG；默认输出在模块所在项目的 outputs/assignment_analysis 下。


## 输出目录

默认导出至项目 outputs/assignment_analysis：

```text
pbs/                  PBS 单课程表格和图形
treaty/               Treaty 全 term 表格和图形、term 清单及汇总
  terms/<完整开课代码>/ 各 term 的表格和图形
combined/             两门课分行的 course_summary、全局日期核查、数据质量表、metadata、README
```

combined 是跨课程汇总与核查目录，不会把两门课程混成同一学生样本计算。Python 筛选接口与统计口径保持不变。
