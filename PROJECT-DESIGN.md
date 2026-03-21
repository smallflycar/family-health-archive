# family-health-archive 项目设计决议

> 这个文件用于持续记录已经确认的项目设计，避免后续开发遗忘或漂移。

## 项目定位

- 这是一个基于 OpenClaw 的**家庭健康/医疗档案项目**。
- 目标是让家庭中的一个 OpenClaw 部署，变成一个低频、本地优先的健康档案管理系统。
- 项目最终要放到 GitHub 开源，并支持作为多个 skill 的组合项目使用。
- 技能市场分发单位是单个 skill；仓库可以包含多个 skill。

## 基本架构

### 代码层
- 仓库负责承载 skill、脚本、schema、说明文档。
- 仓库不是用户数据目录。

### 数据层
- 使用 SQLite + 本地文件。
- 不依赖常驻数据库服务。
- 数据目录独立于代码目录。
- 默认放在 workspace 外。

推荐默认数据根目录：
- macOS / Linux: `~/.family-health-data/`
- Windows: `%USERPROFILE%\\.family-health-data\\`

目录结构：

```text
<data_root>/
  archive.db
  files/
```

含义：
- `archive.db`：结构化健康档案数据库
- `files/`：用户原始上传文件
- 数据库中的 `documents.file_relpath` 指向 `files/` 下的原始文件

初始化规则：
- 首次使用时自动创建数据目录
- 自动创建 `files/`
- 自动初始化 `archive.db`

## 数据模型

### 1. people / 档案
用于表示家庭成员档案。

可选补充层：
- 可记录基础家庭关系事实，用于后续 skill 更安全地理解亲属称呼
- 关系事实应是稳定关系，不是“我妈 / 我外婆”这种相对称呼本身

当前确认字段：
- `id`
- `display_name`
- `aliases_json`
- `sex`
- `dob`
- `height_cm`
- `current_weight_kg`
- `notes`

### 2. documents / 原始文件层
documents 就是上传的原始文件层。
作用：
- 保存原始文件来源
- 建立 observation 的追溯源头
- 做硬去重

当前确认字段：
- `id`
- `person_id`
- `title`
- `occurred_on`
- `file_relpath`
- `sha256`
- `mime_type`

说明：
- 不再强调 `doc_type`
- documents 保持轻量，不承担主要结构化语义
- OCR 不是主索引策略，当前不作为核心依赖

### 3. observations / 结构化结果层
observation 不是单个指标，而是一份可独立理解的结构化结果单元。

例如：
- 一张血脂化验单 -> 1 条 observation
- 一张血常规 -> 1 条 observation
- 一份体检 PDF 中的多个项目 -> 多条 observation，共享同一 source document

当前确认 observation 顶层字段：
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

### report_type 规则
- 自由文本
- 尽量归一化
- 同类不同名尽量识别为同一种
- 不做封闭枚举

### items_json 规则
- `items_json` 是 JSON 数组
- 数组中的每个对象表示一个独立指标/结果项

数值型项尽量包含：
- `name`
- `value`
- `unit`
- `reference_range`
- `flag`

文字型项尽量包含：
- `name`
- `text`

### extra_json 规则
- 存不适合进固定字段、也不适合混进 `items_json` 的额外信息

## 关系定义

- 一个 `people` -> 多个 `documents`
- 一个 `documents` -> 零个或多个 `observations`

## 提取策略

### 多模态优先
- 对图片、手机截图、单页医疗报告，优先使用多模态模型直接理解与提取
- 不把 OCR 作为默认前提
- OCR 可以作为未来兼容/回退能力，但不是当前主设计

### PDF 处理原则
- 单页 PDF：可按单页报告直接提取
- 多页 PDF（如体检总报告）：允许上传同一个 source document，再拆成多个 observation
- 项目不应默认假设所有模型都能直接稳定处理 PDF 原始二进制
- 更稳妥的实现方向是：把 PDF 视为文档容器，再根据运行环境选择直接多模态处理、页面转图片处理、或后续兼容回退方案

当前 manager 侧约定：
- 图片/截图提取结果使用 `image_report` JSON shape，且必须只包含 1 条 observation
- PDF 拆分提取结果使用 `pdf_split_report` JSON shape，可包含多条 observation，共享同一个 source document
- OpenClaw 当前使用的多模态模型直接负责图片/PDF理解与结构化输出
- 模型输出应收口成一个医疗归档结果 JSON，再由本地脚本校验并写入导入链
- 写库前先走 `medical_file_gate`
- `medical_file_gate` 可以先是保守 stub，但 gate 不是 `accepted_medical_file` 时不得入库
- 如果还没有确定档案归属，可在 payload 中保留 `person_match` 占位状态；此时允许校验，但不得入库

### OpenClaw / 模型兼容立场
- 项目默认趋势是假设 OpenClaw 会越来越多地运行支持多模态的大模型
- v1 默认依赖 OpenClaw 用户当前使用的模型完成多模态理解
- 不额外引入外部模型服务，也不要求单独配置另一套模型
- schema、归档流程、数据目录和 skill 设计应与具体模型品牌解耦，但以 OpenClaw 模型输出为默认前提
- OCR / 单独 PDF 回退策略暂不作为 v1 主设计

## 用户体验目标（当前确认）

### 安装后的默认行为
- 用户安装这一组 skill 后，不应手动先创建数据库文件
- skill 在首次需要读写档案时，应自动检查默认数据根目录
- 如果不存在数据目录或 `archive.db`，则自动创建数据目录、`files/` 与数据库文件

### 用户期望的主流程
用户直接发送医疗数据文件，系统自动进入归档流程。

### 医疗相关性触发门槛
即使用户安装了这组 skill，也不能对所有图片/PDF都自动启动医疗归档流程。

必须先判断上传内容是否明显属于医疗相关资料，例如：
- 化验单
- 检查报告
- 医院/体检中心 PDF
- 处方、检验结果、影像/超声/心电图报告

只有当文件明显是医疗数据时，才进入后续流程：
- 识别人
- 匹配/创建档案
- 提取结构化结果
- 写入数据库

如果文件不是医疗相关内容：
- 不触发归档流程
- 不写入健康档案数据库
- 让其他正常 skill / 普通工作流继续处理

这条规则非常重要，因为用户可能只是把这组 skill 安装在一个原本已经有很多其他 skill 的 OpenClaw 环境中。

#### 场景 A：图片
包含：
- 照片
- 手机截图

默认产品假设：
- 一张图片对应一张化验单/一份单独报告

流程：
1. 自动识别医疗数据中的人
2. 如果已有匹配档案，直接归到该人的档案下
3. 如果没有匹配档案，提示是否创建新档案
4. 创建后继续归档
5. 自动提取结构化结果并写入数据库

#### 场景 B：PDF
典型场景：医院或体检机构导出的完整体检报告 PDF

默认产品假设：
- 一个 PDF 可以包含多个项目/多个报告结果单元
- 这些结果单元应该分别拆成多个 observation
- 但它们都链接回同一个 source document（该 PDF）

流程：
1. 接收 PDF 作为一个 source document
2. 识别其中的多个结果单元
3. 每个结果单元单独结构化并写为 observation
4. 所有 observation 共用同一个 source_doc_id

### 手动建档
- 用户可以直接手动创建档案
- 通过输入基础档案信息建立 `people` 记录

## 归档原则

### 准确性优先
- 如果上传文件模糊、缺失、错乱、身份不明、日期不清、结果内容不可靠：
  - 不入库
  - 要求用户重新上传完整清晰的整份报告
- 不能因为一部分区域清楚，就只提取清楚部分后归档
- 不保存半成品 observation
- 不先入库后修正

### 档案优先
- 所有数据都必须归到某个人的档案下
- 如果能够自动识别归属，就直接归档
- 如果没有匹配档案，提示用户是否创建新档案
- 创建后再归档

### 误归档修正不是主流程
- 设计目标是归档时就尽量保证正确
- 不以“先乱收后修正”为系统设计基础

## 去重策略

### 硬去重
- 同一文件 `sha256` 相同 -> 不重复存储

### 软去重
- 即使文件不同，如果本质上是同一份报告/同一份医疗数据，也应识别为重复
- 默认保守：宁可提示疑似重复，也不要重复污染数据

当前确认的软去重思路：
- 同一个 `person_id`
- 同一个 `observed_on`
- 同一个 `report_type`
- `accession_no` 相同时优先认为是强疑似重复
- 即使图片不同、指标不完全对齐，只要同人同日同项目，也先作为疑似重复提示用户确认

## Skill 职责

### manager skill
负责完整入库链路：
- 建档 / 找人
- 上传校验
- 硬去重
- 软去重
- 结构化提取
- 写入 documents
- 写入 observations
- 向用户反馈结果

### assistant skill
负责只读使用：
- 档案查看
- 搜索
- 时间线
- 总结
- 复诊准备

## 交接说明

- 当前项目已经进入“有真实实现骨架”的阶段，不是纯文档状态
- 若切换到其他会话、其他模型或直接用 Codex 接手，请优先读取：
  - `README.md`
  - `PROJECT-DESIGN.md`
  - `HANDOFF.md`
  - `skills/health-archive-manager/references/schema.md`
  - `skills/health-archive-manager/references/medical-archive-result.md`
  - `skills/health-archive-manager/references/model-output-guidelines.md`
  - `skills/health-archive-manager/references/medical-archive-result-image.md`
  - `skills/health-archive-manager/references/medical-archive-result-pdf.md`

## 开发方式决议

- 已确定的设计，尽快同步写入项目文件
- 尽量减少反复就低层细节询问用户
- 默认由代理先做高层整合与实现，用户主要负责纠偏和方向确认
- 需要等待用户确认的，只保留真正影响产品方向的问题

## 当前实现推进记录

### 已落地的脚本能力（第一轮）
- 初始化共享数据根目录
- 初始化新版 schema
- 创建档案（people）
- 添加原始文件 document
- 添加 observation

### 已落地的脚本能力（第二轮）
- 列出 documents
- 列出 observations
- observation 摘要输出
- 基于 accession_no / 同人同日同类型 / items_json 规范化比较的软去重初版
- `import-structured-result` 桥接命令：把已提取的结构化结果一次性写入 document + observation

### 已落地的脚本能力（第三轮）
- `import-medical-archive-result` 对 gate reject / manual review / person profile pending 给出更清晰的 `not_imported` 原因
- payload 校验阶段支持 `person_match` 占位，贴近最终产品的人档案匹配流程

### 已落地的脚本能力（第四轮）
- `extract_medical_file.py`：本地开发桥接脚本，可把一份模型风格 JSON 收口成校验后的医疗归档结果 JSON
- manager 侧已有基础 profile match：按 `display_name` / `aliases_json` 做精确匹配，返回 `matched_existing_profile` / `needs_profile_selection` / `needs_profile_creation`
- 模型结构化结果与共享 SQLite 档案打通，不再只停留在 contract / importer 层
- 新的首选模型输出合同：`medical-archive-result/v1`
