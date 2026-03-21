# Medical Analysis Result JSON: `medical-analysis-result/v1`

This is the assistant-side analysis-layer JSON.

Purpose:
- read archived structured observations from SQLite
- normalize them into reusable domain series
- support later summary / chart / follow-up outputs

This is not the raw archive import payload.
This sits after archive ingestion and before user-facing explanation or visualization.

## Required top-level fields

- `schema_version` = `medical-analysis-result/v1`
- `domain`
- `person`
- `series`
- `observation_count`

## `person`

Contains profile basics for the selected archive person.

Expected fields:
- `id`
- `display_name`
- `aliases`
- `sex`
- `dob`
- `height_cm`
- `current_weight_kg`

## `series`

Each entry represents one normalized metric series.

Expected fields:
- `metric_key`
- `label`
- `unit`
- `points`

## `points`

Each point should represent one archived structured value.

Expected fields:
- `date`
- `value`
- `raw_value`
- `reference_range`
- `flag`
- `source_observation_id`
- `source_report_type`
- `source_title`

## Initial domains

The first implementation only needs a small fixed registry.

Recommended starting domains:
- `lipids`
- `glucose`
- `blood_pressure`
- `weight`

Each domain may expose only the metrics that are actually found in the archive.

## Example

```json
{
  "schema_version": "medical-analysis-result/v1",
  "domain": "lipids",
  "person": {
    "id": "11111111-1111-1111-1111-111111111111",
    "display_name": "成员A",
    "aliases": [],
    "sex": "女",
    "dob": "1958-03-01",
    "height_cm": null,
    "current_weight_kg": null
  },
  "observation_count": 3,
  "series": [
    {
      "metric_key": "ldl_c",
      "label": "低密度脂蛋白胆固醇",
      "unit": "mmol/L",
      "points": [
        {
          "date": "2026-03-18",
          "value": 4.12,
          "raw_value": "4.12",
          "reference_range": "0-3.40",
          "flag": "↑",
          "source_observation_id": "obs-1",
          "source_report_type": "lipid panel",
          "source_title": "血脂检验"
        }
      ]
    }
  ]
}
```
