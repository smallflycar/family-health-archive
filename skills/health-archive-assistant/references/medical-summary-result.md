# Medical Summary Result JSON: `medical-summary-result/v1`

This is the assistant-side summary-layer JSON.

Purpose:
- reorganize analysis/context data into a compact fact summary
- support later natural-language answers from the model
- keep user-facing explanation flexible while making core facts stable

## Required top-level fields

- `schema_version` = `medical-summary-result/v1`
- `scope`
- `person`
- `key_facts`
- `trend_highlights`
- `history_highlights`
- `source_refs`

Optional:
- `focus_domain`
- `caution_flags`

## `scope`

Recommended initial values:
- `person_overview`
- `domain_overview`

## `key_facts`

Short fact items that are still archive-grounded.

Expected fields:
- `label`
- `fact_text`

## `trend_highlights`

Short fact items derived from recent trend data.

Expected fields:
- `metric_key`
- `label`
- `summary_text`
- `latest_value_text`

## `history_highlights`

Longer-horizon fact items based on history candidates.

Expected fields:
- `label`
- `summary_text`
- `observed_on`

## `caution_flags`

Simple structured reminders for later model answers.

Expected fields:
- `type`
- `text`

## Example

```json
{
  "schema_version": "medical-summary-result/v1",
  "scope": "person_overview",
  "person": {
    "id": "11111111-1111-1111-1111-111111111111",
    "display_name": "成员A"
  },
  "key_facts": [
    {
      "label": "最近报告数",
      "fact_text": "最近档案中有 6 份已归档报告。"
    }
  ],
  "trend_highlights": [
    {
      "metric_key": "ldl_c",
      "label": "低密度脂蛋白胆固醇",
      "summary_text": "最近一次低密度脂蛋白胆固醇仍高于建议上限。",
      "latest_value_text": "4.12 mmol/L"
    }
  ],
  "history_highlights": [
    {
      "label": "长期病史候选",
      "summary_text": "2014-06-03 胃镜检查提示胃溃疡，建议随访治疗。",
      "observed_on": "2014-06-03"
    }
  ],
  "caution_flags": [
    {
      "type": "archive_incomplete_record",
      "text": "这只是基于已归档资料的总结，不等于完整医院病历。"
    }
  ],
  "source_refs": []
}
```
