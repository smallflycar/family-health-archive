# Family Health Archive SQLite schema (draft v2)

Goal: stable, reusable, and friendly to first-party and third-party OpenClaw skills.

This schema is intended to be the shared archive protocol for the whole project.

## Data root

Recommended data root:
- macOS / Linux: `~/.family-health-data/`
- Windows: `%USERPROFILE%\\.family-health-data\\`

Expected layout:

```text
<data_root>/
  archive.db
  files/
```

## Table overview

- `people`: family member profiles / 档案
- `person_relationships`: basic family relationship facts / 基础家庭关系事实
- `documents`: original uploaded files / 原始文件来源层
- `observations`: structured medical result units / 结构化结果层

Relationships:
- one `people` row -> many `documents`
- one `documents` row -> zero or many `observations`
- `person_relationships` links one profile to another with a stable family relation fact

---

## people

Family member profile records.

- `id` TEXT PRIMARY KEY (uuid)
- `display_name` TEXT NOT NULL  -- 档案显示姓名
- `aliases_json` TEXT           -- 别名 JSON 数组
- `sex` TEXT                    -- 性别
- `dob` TEXT                    -- 出生日期 YYYY-MM-DD
- `height_cm` REAL              -- 身高（厘米）
- `current_weight_kg` REAL      -- 当前体重（千克）
- `notes` TEXT                  -- 档案备注
- `created_at` TEXT NOT NULL    -- 技术字段，ISO8601

Suggested indexes:
- `people(display_name)`

---

## documents

Original uploaded file layer.

This table is intentionally lightweight.
It is used for provenance, file storage, and hard de-duplication.
Classification and structured semantics mainly live in `observations`.

- `id` TEXT PRIMARY KEY (uuid)
- `person_id` TEXT NOT NULL REFERENCES people(id)  -- 所属家庭成员ID
- `title` TEXT                                     -- 文件标题
- `occurred_on` TEXT                               -- 文件对应日期 YYYY-MM-DD
- `file_relpath` TEXT NOT NULL                     -- 原始文件相对路径（相对于 data_root）
- `sha256` TEXT NOT NULL                           -- 文件哈希值
- `mime_type` TEXT                                 -- 文件类型，如 image/png / application/pdf
- `created_at` TEXT NOT NULL                       -- 技术字段，ISO8601

Suggested indexes:
- `documents(person_id, occurred_on)`
- `documents(sha256)` UNIQUE

---

## person_relationships

Basic family relationship facts between profiles.

This table is for stable facts such as parent/child/spouse relationships.
It should not directly store speaker-relative phrases like "my grandma".

- `id` TEXT PRIMARY KEY (uuid)
- `subject_person_id` TEXT NOT NULL REFERENCES people(id)
- `relation_type` TEXT NOT NULL
- `object_person_id` TEXT NOT NULL REFERENCES people(id)
- `notes` TEXT
- `created_at` TEXT NOT NULL

Suggested indexes:
- `person_relationships(subject_person_id)`
- `person_relationships(object_person_id)`

Recommended initial `relation_type` values:
- `mother_of`
- `father_of`
- `daughter_of`
- `son_of`
- `spouse_of`

---

## observations

Structured medical result units.

One row represents one independently understandable report/result unit.
Examples:
- one lipid panel report
- one CBC report
- one liver function report
- one ultrasound result block extracted from a physical exam PDF

This is **not** a single-metric table.

### Fixed top-level fields

- `id` TEXT PRIMARY KEY (uuid)
- `person_id` TEXT NOT NULL REFERENCES people(id)          -- 所属家庭成员ID
- `source_doc_id` TEXT NOT NULL REFERENCES documents(id)   -- 来源原始文件ID
- `report_type` TEXT NOT NULL                              -- 报告类型（自由文本，尽量归一化）
- `title` TEXT                                             -- 标题 / 结果名称
- `observed_on` TEXT                                       -- 检查日期 / 结果日期 YYYY-MM-DD
- `patient_name` TEXT                                      -- 报告上的姓名
- `patient_sex` TEXT                                       -- 报告上的性别
- `patient_age_text` TEXT                                  -- 报告上的年龄原文
- `patient_dob` TEXT                                       -- 报告上的出生日期 YYYY-MM-DD
- `hospital_name` TEXT                                     -- 医院 / 机构名称
- `department_name` TEXT                                   -- 科室名称
- `doctor_name` TEXT                                       -- 医生姓名
- `specimen_type` TEXT                                     -- 标本类型
- `accession_no` TEXT                                      -- 样本号 / 检验号 / 报告号
- `items_json` TEXT NOT NULL                               -- 指标数据 JSON 数组
- `extra_json` TEXT                                        -- 补充信息 JSON 对象
- `created_at` TEXT NOT NULL                               -- 技术字段，ISO8601

Suggested indexes:
- `observations(person_id, observed_on)`
- `observations(source_doc_id)`
- `observations(report_type)`
- optional composite: `observations(person_id, observed_on, report_type)`

### `items_json` shape

`items_json` should be a JSON array.
Each array element is one independent metric/result item.

Numeric example:

```json
[
  {
    "name": "低密度脂蛋白胆固醇",
    "value": "4.12",
    "unit": "mmol/L",
    "reference_range": "0-3.40",
    "flag": "↑"
  }
]
```

Text result example:

```json
[
  {
    "name": "心电图结论",
    "text": "窦性心律，大致正常心电图"
  }
]
```

### `extra_json` shape

`extra_json` is for uncommon, report-specific, or overflow fields that do not belong in fixed top-level columns and should not be mixed into `items_json`.

Examples:
- remarks
- method
- package name
- report footer notes
- device/model-specific fields

---

## De-duplication guidance

### Hard duplicate
At the `documents` layer:
- same `sha256` => same file => do not store twice

### Soft duplicate
At the `observations` layer:
Treat as suspected duplicate by default when these strongly match:
- same `person_id`
- same `observed_on`
- same `report_type`
- same or highly similar structured content in `items_json`
- matching `accession_no` when present

The default product stance is conservative:
- avoid duplicate medical data
- if suspected duplicate, show the existing record and stored items, then ask the user to confirm

For v1 duplicate detection:
- same `person_id`
- same `observed_on`
- same `report_type`

is already sufficient to trigger suspected duplicate by default, even if the uploaded image differs or items are not perfectly aligned yet.

---

## Manager import payloads

The shared archive schema stays at the SQLite layer, but the manager skill also needs a stable medical archive result payload contract before inserting rows.

Current reference payloads:
- `medical-archive-result.md`
- `medical-archive-result-image.md`
- `medical-archive-result-pdf.md`

Required top-level payload fields:
- `schema_version` = `medical-archive-result/v1`
- `flow` = `image_report` or `pdf_split_report`
- `person_id` when an existing profile is already matched
- `source_file`
- `medical_file_gate`
- `document`
- `observations`

Optional workflow field:
- `person_match`

`person_match.status`:
- `matched_existing_profile`
- `needs_profile_selection`
- `needs_profile_creation`

`medical_file_gate` minimum fields:
- `decision` = `accepted_medical_file` / `rejected_not_medical` / `needs_manual_review`
- `source_kind` = `image` / `screenshot` / `pdf`

Flow rules:
- `image_report` -> exactly one observation
- `pdf_split_report` -> one or more observations, all linked to the same imported document row
- unresolved `person_match` payloads may validate successfully, but import should stop before any write happens

---

## Project stance

- keep schema stable and shared across skills
- keep `documents` lightweight
- keep `observations` dynamic but queryable
- prefer profile-first archive flows
- prioritize accuracy over permissive ingestion
