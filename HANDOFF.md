# HANDOFF.md

> 给后续继续开发这个项目的人（包括 Codex / 你自己）的交接说明。

## 项目目录

当前项目目录：
- `/home/litchi/.openclaw/workspace/family-health-archive`

OpenClaw workspace：
- `/home/litchi/.openclaw/workspace`

## 项目目标（最终形态）

这个项目最终成品不是单个脚本，而是：

> **一组开箱可用的 OpenClaw skills，建立在一个统一的、结构化的、本地家庭健康档案数据库之上。**

用户安装这组 skill 后，应该可以：
- 手动创建家庭成员档案
- 直接发送医疗相关图片/截图/PDF
- 自动识别是否为医疗相关文件
- 对可靠文件自动提取结构化数据
- 如果已有对应档案，直接归档到该人名下
- 如果没有对应档案，提示是否创建新档案
- 将原始文件作为 `document` 存储
- 将结构化结果作为一个或多个 `observation` 存储
- 之后由其他 skill 继续完成查询、总结、复诊准备等能力

## 核心设计原则

### 1. skill 套件 + 共享数据库
- 最终交付形态是一组 skill
- 这些 skill 共享同一个数据库和文件数据根目录
- 数据结构应稳定、公开、可复用
- 第三方 skill 理论上也可以基于这套 schema 读写

### 2. 本地优先 / 低频使用
- SQLite + 本地文件
- 不依赖常驻数据库服务
- 不引入 PostgreSQL/MySQL/Docker daemon

### 3. 数据目录与代码目录分离
- 项目代码目录 != 用户数据目录
- 默认数据根目录在 workspace 外
- 推荐默认位置：
  - Linux/macOS: `~/.family-health-data/`
  - Windows: `%USERPROFILE%\\.family-health-data\\`

目录结构：

```text
<data_root>/
  archive.db
  files/
```

含义：
- `archive.db` 保存结构化档案数据
- `files/` 保存原始图片 / 截图 / PDF
- 两者属于同一个用户数据根目录，但代码仓库本身不承载用户数据

首次使用时应自动：
- 创建数据目录
- 创建 `files/`
- 初始化 `archive.db`

### 4. 档案优先
- 所有医疗数据都必须归属于某个人的档案
- 如果能匹配已有档案，直接归档
- 如果没有匹配档案，提示是否创建新档案
- 不应该在正常用户流里长期保留“未归属数据”

### 5. 准确性优先
- 如果图片/PDF 模糊、缺失、身份不明、日期不清、内容不可靠：
  - 不归档
  - 不保存半成品 observation
  - 提示用户重新上传
- 不以“先乱收后修正”为设计基础

### 6. 医疗相关性触发门槛
- 这组 skill 不能对所有图片/PDF 自动触发
- 只有判断上传文件明显属于医疗相关资料时，才进入归档流程
- 否则不应打断原本 OpenClaw 环境里的其他工作流

### 7. 多模态优先
- 图片/截图/报告照片优先使用多模态模型直接理解与提取
- OCR 不是默认前提
- 但项目不能写死依赖某一类特定模型能力
- 数据模型必须和提取方式解耦

## 当前确认的数据模型

### people
家庭成员档案。

当前字段：
- `id`
- `display_name`
- `aliases_json`
- `sex`
- `dob`
- `height_cm`
- `current_weight_kg`
- `notes`
- `created_at`

### documents
原始文件来源层。
作用：
- 保存原始上传文件
- 提供 observation 溯源
- 做文件级硬去重

当前字段：
- `id`
- `person_id`
- `title`
- `occurred_on`
- `file_relpath`
- `sha256`
- `mime_type`
- `created_at`

说明：
- documents 保持轻量
- 不再以 `doc_type` 作为核心
- OCR 不作为主索引依赖

### observations
结构化结果层。

一条 observation = 一份可独立理解的结果单元。
不是一指标一行。

例如：
- 一张血脂化验单 -> 一条 observation
- 一张血常规 -> 一条 observation
- 一个体检 PDF -> 多条 observation，共享同一个 source document

当前顶层字段：
- `id`
- `person_id`
- `source_doc_id`
- `report_type`
- `title`
- `observed_on`
- `patient_name`
- `patient_sex`
- `patient_age_text`
- `patient_dob`
- `hospital_name`
- `department_name`
- `doctor_name`
- `specimen_type`
- `accession_no`
- `items_json`
- `extra_json`
- `created_at`

### report_type 规则
- 自由文本
- 尽量归一化
- 不做封闭枚举

### items_json 规则
`items_json` 是 JSON 数组。
每个对象是一项独立指标/结果。

数值型项尽量包含：
- `name`
- `value`
- `unit`
- `reference_range`
- `flag`

文字型项尽量包含：
- `name`
- `text`

### extra_json
放不适合固定字段、也不适合混进 `items_json` 的额外信息。

## 输入与产品行为

### 图片 / 截图
- 默认产品假设：一张图片 = 一张单独报告/化验单
- 流程：
  1. 判断是否医疗相关
  2. 判断是否清晰/可靠
  3. 提取结构化结果
  4. 识别人
  5. 匹配已有档案或提示建档
  6. 写入一个 source document + 一个 observation

### PDF
- 典型场景：体检中心/医院完整体检报告 PDF
- 默认产品假设：一个 PDF 可能包含多个结果单元
- 流程：
  1. 作为一个 source document 接收 PDF
  2. 拆分其中的多个结果单元
  3. 每个结果单元单独写为 observation
  4. 所有 observation 共用同一个 `source_doc_id`

## 去重策略

### 硬去重
- 同一文件 `sha256` 相同 -> 不重复存储

### 软去重
- 即使文件不同，如果本质是同一份医疗结果，也应识别为重复
- 当前思路：
  - 同 `person_id`
  - 同 `observed_on`
  - 同 `report_type`
  - `items_json` 内容相同或高度相似
  - `accession_no` 相同时优先认为强疑似重复

## 当前仓库已经完成的东西

### 文档 / 设计层
已更新：
- `README.md`
- `PROJECT-DESIGN.md`
- `skills/health-archive-manager/SKILL.md`
- `skills/health-archive-assistant/SKILL.md`
- `skills/health-archive-manager/references/medical-archive-result.md`
- `skills/health-archive-manager/references/model-output-guidelines.md`
- `skills/health-archive-manager/references/schema.md`
- `skills/health-archive-manager/references/medical-archive-result-image.md`
- `skills/health-archive-manager/references/medical-archive-result-pdf.md`

### 脚本 / CLI 层
核心脚本：
- `skills/health-archive-manager/scripts/archive_db.py`
- `skills/health-archive-manager/scripts/extract_medical_file.py`

当前已具备的能力：
- 初始化共享数据根目录
- 初始化 SQLite schema
- 创建 people 档案
- 按提取到的人名精确匹配已有档案（display_name / alias）
- 添加 document
- 添加 observation
- 列出 people / documents / observations
- image / pdf 的 `medical-archive-result/v1` 导入
- PDF split 的一文档多 observation 导入
- 初步 medical gate stub
- 更明确的 ingest outcome
- `person_match` 占位 contract
- 本地开发桥接脚本：可把一份模型风格 JSON 收口为带 `person_match` 的医疗归档结果 JSON
- 基础软去重

### 测试
测试文件：
- `tests/test_archive_db.py`

已通过测试（最近一轮）：
- 7 tests passed

## 当前还没完成的关键缺口

### 1. 真正的多模态提取器
现在已有：
- extraction-result contract
- importer
- `extract_medical_file.py` 本地开发桥接层（模型结果 JSON + person match）

仍然还没有：
- 更贴近 OpenClaw skill 实际提示词/工作流的模型输出规范
- 从 OpenClaw 对话流直接过渡到归档 JSON 的完整产品说明

### 2. 真实的人物匹配/建档交互流
现在已有基础自动匹配：
- 精确 display name
- 精确 alias

但还没有完整的：
- 多候选时的正式用户选择动作
- 无匹配时的建档确认后继续归档
- 确认动作与最终 import 的一体化产品流

### 3. 更完整的 gate / reject / re-upload 消息层
原则已定，但实际产品消息流还没完整做完。

### 4. 更干净的软去重最终确认流程
当前导入链已经有软去重，但若希望在“重复确认前不先落 source document”，还需要再收口。

## 推荐下一步开发顺序

1. **实现真正的模型归档输出层**
   - 图片/截图 -> OpenClaw 多模态模型 -> `medical-archive-result/v1`
   - PDF -> OpenClaw 多模态模型 -> 多 observation 提取

2. **实现真实 person/profile flow**
   - 提取结果里的人名与已有档案匹配
   - 无匹配时返回可交互的建档动作

3. **把 gate / reject / re-upload 交互做成完整产品流**

4. **最后再做开源发布收尾**
   - 命名统一
   - 安装说明
   - skill 打包检查
   - 示例工作流说明

## 说明

本仓库当前已经不是“纯讨论状态”，而是有真实代码、文档、contract、importer 和测试的实现状态。
但它还不是最终开箱即用成品，离真正发布还差“OpenClaw 模型输出规范 + 档案匹配/建档交互 + 更完整产品流”这几步。
