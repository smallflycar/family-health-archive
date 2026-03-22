---
name: health-archive-assistant
displayName: 家庭健康助手
description: 读取共享的本地健康档案，并生成分析、总结和图表数据。
tags: 医疗, 健康档案, 家庭, 分析, 图表
---

# Health Archive Assistant

这是读取侧 skill，默认只读。

它的职责不是写库，而是优先使用本地健康档案回答问题、整理历史、生成分析层结果和展示层数据。

## 数据位置

推荐默认位置：

- macOS / Linux: `~/.family-health-data/`
- Windows: `%USERPROFILE%\\.family-health-data\\`

目录结构：

```text
<data_root>/
  archive.db
  files/
```

## 前置依赖

这个 skill 读取共享档案，推荐与 `health-archive-manager` 一起安装。

如果本地还没有初始化的档案目录或 `archive.db`：

- 不要假装有档案数据
- 应提示用户安装并使用 `health-archive-manager` 初始化档案

## 读取原则

只要用户在询问家庭成员的健康情况、历史、趋势、复诊准备、风险提醒、既往检查结果，就应优先读取本地档案，而不是绕过数据库直接凭模型常识回答。

## 共享 Schema

读取共享 schema，而不是私有 schema。

如果字段细节重要，先看：

- `../health-archive-manager/references/schema.md`

## 主要职责

- 成员档案概览
- 查询某位成员的历史报告
- 生成人物时间线
- 整理结构化 observation
- 生成可复用分析 JSON
- 生成病史上下文 JSON
- 生成总结层 JSON
- 生成图表 spec
- 在对话里基于本地档案做中文解释

## 数据模型

### `people`

成员档案。

### `documents`

原始文件层，主要用于：

- provenance
- 文件引用
- 回看原件

### `observations`

主要查询层。

一个 observation 表示一份独立可理解的结果单元，而不是“一项指标一行”。

## 查询顺序

1. 识别目标成员
2. 优先查询 `observations`
3. 需要追溯时再回到 `documents`
4. 需要原件时再使用文件路径或原始文件引用

## 分析层

在生成总结、图表、复诊准备之前，优先先提取可复用的中间结果。

参考：

- `references/medical-analysis-result.md`
- `references/patient-context-result.md`
- `references/medical-summary-result.md`
- `references/display-guidelines.md`
- `references/chart-spec.md`
- `references/response-guidelines.md`

当前已支持的分析领域：

- `lipids`
- `glucose`
- `blood_pressure`
- `weight`

相关脚本：

- `scripts/archive_analysis.py --person-id ... --domain ...`
- `scripts/archive_patient_context.py --person-id ...`
- `scripts/archive_summary.py --person-id ...`
- `scripts/render_chart_spec.py --json-file ... --output-html ...`

## 展示方向

用户可见结果默认遵循这些原则：

- 中文优先
- 解释型优先
- 一张图默认只表达一个关键点
- 默认避免拥挤的多序列图表
- 图只负责展示，解释由对话中的模型完成

## 回答护栏

最终回答仍由模型完成，但必须保留这些底线：

- 先查本地档案
- 区分档案事实和模型解释
- 不替代医生诊断
- 遇到急症风险时更保守

## 推荐输出

### 成员概览

- 基础档案
- 最近归档报告类型
- 最近 observation 日期
- 近期值得关注的结果类别

### 时间线

按 `observed_on` 排序，包含：

- 日期
- 报告类型
- 标题
- 简短结论
- 来源文件引用

### 复诊准备

- 适用于谁
- 相关报告类型
- 最近结构化结果
- 值得带给医生看的异常项
- 可追溯的来源

## 行为限制

- 默认不修改档案数据
- 不假设一定存在 OCR 文本
- 不把 `observations` 当成一项指标一行
- 不依赖封闭的 `report_type` 枚举

## 安装与协作

- 本 skill 负责读取、分析和展示
- `health-archive-manager` 负责初始化档案并写入数据
- 两个 skill 共享同一个本地数据目录
- 如果用户只安装了本 skill 且本地档案尚未初始化，应明确提示补装并先使用 `health-archive-manager`
