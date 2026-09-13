# Qualtrics 后端 API

对应 `qualtrics_analysis.py`。本模块提供 Python 接口和批量导出，不包含前端页面、Streamlit 依赖或 HTTP 路由。

## 依赖与输入

基础依赖：`pandas numpy matplotlib`。词云为可选依赖 `wordcloud`。

`load_survey_data(autism_path, treaty_path)` 返回 `(autism_df, treaty_df)`，顺序固定为 Autism、Treaty。输入必须是原始 Qualtrics CSV：第一行为字段代码，第二、三行为题目说明和 Import IDs（读取时跳过）。不能传入已去除这些行的普通 CSV，否则会丢掉两条回答。

课程名称为 `Autism Affirming Practice` 和 `Understanding Treaty`；Autism 标签与 Assignment 模块带 `PBS:` 的名称不同，跨模块时需显式映射。

## 推荐统一入口

```python
import qualtrics_analysis as qa

# 将示例路径换成实际导出文件路径。
autism_df, treaty_df = qa.load_survey_data(
    'Datasets/autism_export.csv', 'Datasets/treaty_export.csv',
)
options = qa.get_course_options()
# [{'value': None, 'label': '整体 / All courses'}, ...]

result = qa.analyze_survey(
    autism_df, treaty_df,
    course=None,                 # None=整体，或 options 中的课程 value
    include_figures=True,        # False 时只计算数据
    include_wordclouds=False,    # 默认跳过词云
)
```

切换课程时重新调用相同入口即可。单课程选择会同时作用于全部统计表、开放题和图形，而不是仅改变图标题。原始 DataFrame 不会被原地修改。非法课程名称抛出 ValueError，不能使用显示 label 代替 value。

### 返回结构

| 键 | 类型 | 内容 |
|---|---|---|
| summary | dict | courses、respondent_rows（各课程原始行数）、valid_likert_responses（题目回答条数）、valid_nps_responses |
| tables | dict[str, DataFrame] | 见下表 |
| figures | dict[str, Figure] | theme_agreement、response_distribution、nps_breakdown；选择生成词云时另含 wordclouds |
| notices | list[str] | 缺列、非法值、无有效回答、缺失词云依赖的提示 |
| qualitative | dict[str, DataFrame] | Q6.0、Q7.0、Q8.0；每表列为 Course、Response |
| long_data | DataFrame | 清洗后的 Course、Code、Response、Dimension、Statement、Score |
| metadata | dict | 课程筛选、量表范围、百分数范围和分析限制 |

`include_figures=False` 时 figures 为空，即使 include_wordclouds=True 也不会生成词云。默认整体两门课均保留在结果中，一门课没有有效数据时显示空状态。调用方应展示 notices 和样本量，不把空值显示为零。

### tables 的结构

| 名称 | 索引／列 | 口径 |
|---|---|---|
| theme_summary | Course 索引；Engagement、Learning experience、Impact、Assessment 四列 | 1～5 的有效题目回答均分，保留两位小数；空组为 NaN |
| nps_summary | Course 索引；n、Promoters %、Passives %、Detractors %、NPS | 有效 Q2 人数；占比为 0～100，保留一位小数；n=0 时比例和 NPS 为 NaN |
| response_distribution | Course/Dimension 多层索引；五个 Likert 标签列 | 各课程主题中有效回答的百分比分布，0～100；无有效回答为 NaN |
| theme_response_counts | Course、Dimension、n 三列 | 各主题有效题目回答条数，无回答为 0；不是受访者人数 |

## 清洗规则与解释

- Likert 题目：Q1_1～Q1_5、Q3.0_1～Q3.0_4、Q4.0_1～Q4.0_5、Q5.0_1～Q5.0_5。两端空格会删除；五个标准英文标签依次映射为 1～5：Strongly disagree、Slightly disagree、Neither agree nor disagree、Slightly agree、Strongly agree。
- 无法识别的非空 Likert 文本被排除并提示，不自动猜测大小写、语言或数字标签的含义。缺失题目补为空值。
- Q2 会转换为数值，仅保留 0～10 的整数；非法文本、越界值、小数排除并提示。空白不算有效回答。
- Promoters=9～10，Passives=7～8，Detractors=0～6；NPS=Promoters %−Detractors %。比例已乘 100，前端不能再次乘 100。合法 NPS 范围为 −100～100。
- 主题均分是所有有效题目回答直接平均，不是先计算每位受访者均分；主题分布的分母也是题目回答数。
- 开放题 Q6.0（How they'll apply it）、Q7.0（Best aspects）、Q8.0（Areas to improve）会去除首尾空白，排除空白回答；缺失列产生空表和提示。
- 没有自动按 Finished/Progress 筛选、去重、检测测试答卷或匿名化文本。原始问卷行数不能自动称为有效独立受访者人数。
- 长表与开放题表没有保留受访者 ID，不能用输出行号做跨表个人匹配。
- 不支持 term 筛选；需先有可靠的问卷 term 字段再扩展。

## 空状态与图形

均分缺主题时显示 N/A；全部无回答时显示 No valid responses。NPS 无有效值时显示 No valid NPS responses。词云无有效词（包括只有停用词）时显示 No usable words。

统一入口请求词云但未安装 wordcloud 时，跳过词云并在 notices 提示，不影响其他结果。直接调用 `plot_wordclouds` 时仍需安装该依赖，否则抛出 ImportError。

单课程词云为 3×1，整体为 3×2。词云使用英文停用词，额外去除 nil、na、n/a、none、will、course、etc，最多 60 个词，random_state=42。词频不等于受访者比例，也不是情感结论。

响应分布图中立比例以 0 为中心，负号表示左侧不同意方向，不代表负比例。百分比标签会四舍五入；占比小的区段可能不标数值。

## 保留的独立函数

| 函数 | 返回 |
|---|---|
| build_long_format(autism_df, treaty_df) | 清洗后的两课长表 |
| get_theme_summary(long_df) | 主题均分表 |
| get_nps_summary(autism_df, treaty_df) | 两课 NPS 表 |
| get_qualitative_responses(autism_df, treaty_df) | 两课开放题字典 |
| plot_theme_agreement(long_df) | 主题均分 Figure |
| plot_response_distribution(long_df) | 响应分布 Figure |
| plot_nps_breakdown(autism_df, treaty_df) | 两课 NPS Figure |
| plot_wordclouds(autism_df, treaty_df) | 两课词云 Figure |

这些独立函数保留原有调用签名。获取筛选和完整校验提示时优先使用 analyze_survey；直接函数可能仅清洗数据而不返回 notices。以下划线开头的函数是内部实现，不应由前端依赖。

## JSON、图片与资源管理

DataFrame 不是可直接发送的 JSON。转换索引表时先 reset_index，空值会转为 null：

```python
import json
table = result['tables']['theme_summary']
payload = json.loads(table.reset_index().to_json(orient='records'))
# response_distribution 同样先 reset_index；theme_response_counts 无需 reset_index。
```

无显示服务器应在导入分析模块前设置 Matplotlib Agg 后端。Figure 的导出与关闭由调用方负责：

```python
from io import BytesIO
import matplotlib.pyplot as plt

images = {}
try:
    for name, fig in result['figures'].items():
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=180, bbox_inches='tight')
        images[name] = buffer.getvalue()
finally:
    for fig in result['figures'].values():
        plt.close(fig)
```

绘图会使用 Matplotlib 全局样式，多线程服务建议串行绘图或独立进程。CSV 文件错误仍通过正常 Python 异常向上传播；服务层自行映射 HTTP 错误。当前接口不要求前端使用特定框架。

## 输出与命令行

```shell
python qualtrics_analysis.py
python qualtrics_analysis.py --course "Understanding Treaty"
python qualtrics_analysis.py --course overall
python qualtrics_analysis.py --autism "Datasets/autism_export.csv" --treaty "Datasets/treaty_export.csv" --output-dir "outputs/qualtrics_analysis"
```

默认运行一次生成以下三个范围，每个目录均有自己的统计表、图片和 metadata：

```text
outputs/
  qualtrics_analysis/
    pbs/
    treaty/
    combined/
```

默认输出根目录固定相对脚本位置：`项目/outputs/qualtrics_analysis`，不随启动目录变化。`--course "Autism Affirming Practice"` 仅生成 pbs，`--course "Understanding Treaty"` 仅生成 treaty，`--course overall` 仅生成 combined；省略 --course 则生成三者。显式传入相对 --output-dir 时，路径相对当前工作目录，仍自动追加对应的范围子目录。

Python API 的 `analyze_survey(..., course=None)` 仍只返回整体分析结果，不会自动批量导出，调用方式没有改变。新增 `export_survey_result(result, output_dir, show_plots=False)` 可将一次结果保存到调用方指定的确切目录，并在完成后关闭该结果中的 Figure；CLI 使用它分别导出三种范围。

省略输入时，只在项目 Datasets 内寻找匹配课程关键词并具有 Q2 列的 CSV。多份导出时应显式指定路径，自动查找不是选择最新版本。

输出包括四张图（可选词云）、四张统计 CSV、三张 qualitative_Q*.csv 和 analysis_metadata.json（汇总、提示与口径）。`--show-plots` 可在本地保存后显示窗口；服务端一般不启用。
