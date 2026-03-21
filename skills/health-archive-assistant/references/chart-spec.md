# Chart Spec JSON: `chart-spec/v1`

This is the first-pass display-layer JSON for assistant-side charts/cards.

Goal:
- keep the rendering layer simple and deterministic
- let the model choose what to explain
- keep the actual chart structure stable and reusable

## Product rule

This spec is for explanation-oriented visuals, not generic BI dashboards.

Defaults:
- one chart = one key point
- one key topic = one visual
- one main metric by default
- all labels in Chinese

## Required top-level fields

- `schema_version` = `chart-spec/v1`
- `chart_type`
- `title`
- `subtitle`
- `series`

Optional:
- `reference_bands`
- `latest_supporting_facts`
- `source_refs`
- `design_tokens`

## Supported initial chart types

- `single_metric_trend_line`
- `dual_metric_trend_line`
- `metric_summary_card`
- `report_timeline_card`

## `series`

Each series contains:
- `metric_key`
- `label`
- `unit`
- `points`

Each point contains:
- `date`
- `value`
- `label`

## `reference_bands`

Optional background or reference guidance.

Each item may contain:
- `label`
- `lower`
- `upper`
- `color_token`

For metrics like LDL-C, a simple upper reference line is often enough.

## `latest_supporting_facts`

Short supporting values shown outside the main chart.

Each item may contain:
- `label`
- `value_text`
- `note`

## Recommended first templates

### 1. Lipids

Default:
- `chart_type` = `single_metric_trend_line`
- primary metric = `ldl_c`
- latest other lipids go into `latest_supporting_facts`

### 2. Glucose

Default:
- `chart_type` = `single_metric_trend_line`
- primary metric = `hba1c` when available, otherwise fasting glucose

### 3. Blood pressure

Default:
- `chart_type` = `dual_metric_trend_line`
- two series only: systolic + diastolic

### 4. Weight

Default:
- `chart_type` = `single_metric_trend_line`

## Example: explanation-first lipid chart

```json
{
  "schema_version": "chart-spec/v1",
  "chart_type": "single_metric_trend_line",
  "title": "低密度脂蛋白胆固醇趋势",
  "subtitle": "更适合观察血脂风险变化",
  "series": [
    {
      "metric_key": "ldl_c",
      "label": "低密度脂蛋白胆固醇",
      "unit": "mmol/L",
      "points": [
        {
          "date": "2026-03-01",
          "value": 3.8,
          "label": "3.80"
        },
        {
          "date": "2026-03-18",
          "value": 4.12,
          "label": "4.12"
        }
      ]
    }
  ],
  "reference_bands": [
    {
      "label": "建议上限",
      "upper": 3.4,
      "color_token": "range_caution"
    }
  ],
  "latest_supporting_facts": [
    {
      "label": "最近一次总胆固醇",
      "value_text": "5.90 mmol/L"
    },
    {
      "label": "最近一次甘油三酯",
      "value_text": "1.80 mmol/L"
    }
  ]
}
```

## Selection rule

When several metrics exist in one domain:
- do not automatically draw all of them together
- select the single most useful primary metric for the question
- move the rest into supporting facts unless the user clearly asks for full comparison
