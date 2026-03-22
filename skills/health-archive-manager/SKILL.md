---
name: health-archive-manager
displayName: 家庭健康归档
description: 将家庭医疗文件归档到共享的本地健康档案。
version: 1.0.1
tags: 医疗, 健康档案, 家庭, 归档, 本地优先
---

# 家庭健康归档

这是写入侧 skill，负责把医疗文件安全、保守地归档到本地健康档案。

## 主要职责

- 初始化共享数据目录
- 创建或匹配成员档案
- 判断文件是否明确属于医疗资料
- 拒绝模糊、截断、不完整的报告
- 检查硬重复和软重复
- 保存原始文件
- 写入 `documents` 和 `observations`

## 数据目录

推荐默认位置：

- macOS / Linux: `~/.family-health-data/`
- Windows: `%USERPROFILE%\\.family-health-data\\`

目录结构：

```text
<data_root>/
  archive.db
  files/
```

首次使用时应由本 skill 负责：

1. 解析数据目录
2. 创建目录
3. 创建 `files/`
4. 初始化 `archive.db`

## 共享 Schema

本 skill 不使用私有 schema，而是共享项目 schema。

相关文件：

- `references/schema.md`

其他 skill 也应复用这套 schema。

## 归档模型

### `people`

家庭成员档案。所有医疗数据都必须归属于某个成员。

### `documents`

原始文件层，用于：

- provenance
- 文件保存
- 硬重复检测

### `observations`

结构化医疗结果层。

一个 observation 表示一份独立可理解的结果单元，不是“一项指标一行”。

例如：

- 一次血脂检查
- 一次血常规
- 一次肝功能
- 体检 PDF 中拆出的一个超声结果块

## 档案优先规则

### 没有人物档案就不要归档

如果没有匹配到成员档案：

- 先要求选择已有档案或创建新档案
- 不要直接写入普通归档

### 人物匹配顺序

1. 精确匹配 `display_name`
2. 精确匹配 alias
3. 文件文本中的强匹配
4. 要求用户选择
5. 没有则要求创建新档案

## 触发边界

只对明确的医疗文件触发。

应触发本 skill 的文件示例：

- 化验单
- 检验报告
- 医院 / 体检 PDF
- 处方
- 影像 / 超声 / ECG 报告

不明确是医疗资料的文件：

- 不进入归档流程
- 不写入本地档案

## 上传质量规则

主规则：

- 如果不能可靠理解，就不要归档

以下情况应直接拒绝并要求重传整份报告：

- 图片模糊
- 关键区域被裁切
- 报告不完整
- 混入多个人
- 一张图中混入多份文件
- 姓名 / 日期 / 结果内容无法整体可靠确认

不要要求用户“补一张角落图”或“补一张姓名图”。

## 准确性优先

如果提取不可靠：

- 不创建半成品 observation
- 不存猜测数据
- 不只归档清楚的一半
- 直接要求重新上传完整清晰的原图或原始 PDF

## 重复检测

### 硬重复

- 同一文件 `sha256` 相同，直接拦截

### 软重复

以下条件强匹配时，默认判为疑似重复：

- 同一个 `person_id`
- 同一个 `observed_on`
- 同一个 `report_type`
- 如有 `accession_no`，相同则更强

不要等待逐项指标对齐后才判重复。

## 提取方式

### 默认依赖 OpenClaw 当前模型

图片、截图、报告照片、兼容 PDF 的理解默认由 OpenClaw 当前使用的模型完成。

本仓库不负责接入外部大模型服务。

### Manager 的输入

本地导入脚本优先接收一份结构化 JSON：

- `references/medical-archive-result.md`
- `references/model-output-guidelines.md`
- `references/medical-archive-result-image.md`
- `references/medical-archive-result-pdf.md`

要求：

- OpenClaw 模型输出 `medical-archive-result/v1`
- 本地脚本负责校验 JSON
- 本地脚本负责人物匹配 / 建档 / 去重 / 入库

### 拒绝规则

如果报告不完整或不可靠：

- 明确返回拒绝原因
- 要求重新上传整份清晰报告
- 不要生成部分 observation

## 关键命令

- `init`
- `add-person`
- `match-person`
- `add-relationship`
- `list-relationships`
- `validate-medical-archive-result`
- `resolve-medical-archive-result-person`
- `create-person-for-medical-archive-result`
- `process-medical-archive-result`
- `import-medical-archive-result`

## 安装与协作

- 本 skill 负责初始化档案并写入数据
- `health-archive-assistant` 负责读取、分析和展示
- 两个 skill 共享同一个本地数据目录
- 如果用户只安装了读取侧 skill 且本地档案尚未初始化，应提示补装并先使用本 skill
