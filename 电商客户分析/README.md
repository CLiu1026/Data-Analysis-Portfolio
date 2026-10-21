# 电商经营指标与客户分层分析

这是用于数据分析实习求职的公开数据实践项目，使用真实交易数据完成从建库到结论的流程。项目已在本机实际运行，数据、SQLite 数据库、SQL、结果文件和离线看板均已生成。它不是企业实习，也没有实际开展客户营销活动。

## 先看成果

双击 `outputs/dashboard.html`，浏览月度金额、RFM 分层和复购矩阵，并用下拉框筛选客户。页面完全离线运行，无需登录或安装可视化软件。

阅读 `outputs/analysis_report.md` 了解问题、口径、结论和运营验证方案。`outputs/summary.json` 是简历数字的直接依据；`outputs/validation.json` 保存 90 项通过的检查。

## 项目问题

1. 月度经营变化是由订单规模还是客单价推动？
2. 哪些客户贡献主要金额，哪些历史高价值客户需要进一步核查？
3. 首次购买后，客户是否在下一个自然月回来购买？
4. 缺失编号、重复明细、取消交易和部分月份会怎样影响结论？

## 数据与来源

数据：Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository，DOI https://doi.org/10.24432/C5BW33。

- 官方页面：https://archive.ics.uci.edu/dataset/352/online+retail
- 下载地址：https://archive.ics.uci.edu/static/public/352/online+retail.zip
- 许可：CC BY 4.0，数据可分享和改编，须保留归属。
- 文件：`data/Online Retail.xlsx`，原始 541,909 行。
- 交易窗口：2010-12-01 至 2011-12-09，币种 GBP。数据来自英国线上礼品零售商，包含批发客户，不能直接代表中国消费电商。
- 文件校验值见 `outputs/audit.json`。

GitHub 同类项目选题参考：https://github.com/aliaiman21/online-retail-customer-analytics （RFM、同期群和 SQL 客户分析）。本交付未复制该仓库代码，也没有复用其结果数字；SQL、运行器及看板为本次重新实现，所有简历数字由官方数据重新计算。没有逐行复现该仓库，因此不声称与其清洗口径或数字一致。

相较只展示 RFM 图表的练习，这里增加了订单粒度汇总、匿名交易与客户分析分离、未观测月份标记、取消金额核对、重复候选的金额敏感性，以及 Pandas 独立对账。

## 文件结构

```text
data/                   原始 ZIP、XLSX、retail.sqlite
sql/01_schema.sql       明细表、订单视图和索引
sql/02_monthly_kpis.sql  月度金额、订单数、客单价、环比
sql/03_rfm.sql           客户 RFM 与分层
sql/04_cohort.sql        同期群复购，区分 0 与未观测
sql/05_customer_concentration.sql  客户金额集中度
sql/06_cancellations.sql 取消交易金额核对
sql/07_segment_summary.sql 分层汇总
sql/08_customer_value_sensitivity.sql 客户取消金额核查
run_analysis.py         导入、执行 SQL、验证和生成看板
outputs/                CSV、JSON、报告、HTML 看板
```

## 复现

本机可双击 `重新运行.command`，使用已有 Codex Python 环境，不修改系统环境。运行器会重建该项目自己的数据库和 CSV，保留原始 XLSX。通常需要几十秒至数分钟。

分析报告是当前版本结果的文字解读，重跑不覆盖它。修改数据或 SQL 口径后，须同步更新报告、看板说明文字和简历数字。

在其他电脑上，进入项目目录，准备 Python 3.10+ 后运行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run_analysis.py
```

Windows 使用 `.venv\Scripts\activate`。原始 XLSX 已包含在本机交付中，有它即可离线重跑；没有时会尝试官方 ZIP 下载，需要网络。数据库采用 SQLite 3.25+，窗口函数依赖这一版本。

单独执行 SQL，不必重跑导入：

```bash
sqlite3 -header -csv data/retail.sqlite < sql/02_monthly_kpis.sql
sqlite3 -header -csv data/retail.sqlite < sql/04_cohort.sql
```

`07`、`08` 依赖运行器生成的 `rfm` 分析表。SQL 使用 SQLite 日期函数；迁移到 MySQL/PostgreSQL 时需要调整日期表达式。

## 关键指标口径

| 指标 | 定义 | 边界 |
| --- | --- | --- |
| 正向金额 | 数量和单价均大于零，非 C 前缀的交易金额 | 包括运费等交易项；未扣取消，不称净收入 |
| 订单数 | 按 InvoiceNo 汇总后计数 | 不能用明细行数替代 |
| 客单价 | 正向金额 / 正向订单数 | 包含匿名订单 |
| RFM 的 R | 2011-12-10 距最近正向订单日期的天数 | 历史截面，不是当前客户状态 |
| RFM 的 F | 可识别客户的去重正向订单数 | 未扣回已取消订单 |
| RFM 的 M | 可识别客户的正向交易金额 | 定位后须结合取消交易复核 |
| 次月复购率 | 首购后下一自然月有正向订单的客户数 / 首购同期群人数 | 首购为窗口内首次；不是固定 30 天复购 |
| 加权 M1 | 完整观测群的复购人数总和 / 同期群人数总和 | 不直接平均各群百分比；排除末端未观测群 |
| 窗口带符号金额 | 正向金额减同一窗口内 C 前缀取消金额 | 没有原订单关联，不等于会计净收入 |

## 清洗与验证

按原始八字段完全相同识别重复候选；分析版本去重，但原始 XLSX 保留。去重不证明这些行一定是录入错误，金额差异见报告。

缺失 CustomerID 不填充伪编号：经营统计仍保留有效匿名交易，客户分层和复购排除匿名交易。取消记录单独保留，不简单删除。数量/单价为零或异常的记录不进入有效交易视图。金额按交易行以 Decimal 四舍五入到便士后汇总，规避浮点累计误差。

90 项检查覆盖订单内客户编号一致性、SQL 与 Pandas 逐订单金额及逐客户频次对账、金额守恒、分层完整性、每个可观测同期群人数、复购率范围和第 0 月、NULL 观测边界、部分月份环比禁用。数据规模和 checks 数量不是业务效果指标。

## 署名与求职使用

本项目由 AI 协助搭建，是学习与作品集实践。不要把它描述成过往公司经历、业务上线或已验证的收益提升。建议先独立复跑、修改一条 SQL 并讲清所有口径，再将其作为个人项目投递。可按照实际掌握程度说明自己负责的内容及 AI 使用方式。

项目源代码按 MIT 许可分享；UCI 原始数据继续适用 CC BY 4.0。MIT 许可不改变原始数据许可。
