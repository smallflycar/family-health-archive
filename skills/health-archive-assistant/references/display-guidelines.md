# Display Guidelines

This file defines the first-pass display rules for user-facing health outputs.

Goal:
- make archived health data readable for ordinary family use
- prefer explanation over raw metric dumping
- keep visuals simple, calm, and consistent

## Core display principles

- use Chinese by default
- explanation-first, not metric-first
- one visual should focus on one key health topic
- one chart should usually focus on one key metric
- avoid dumping four unfamiliar lab lines into one crowded chart
- plain-language takeaway should live in the model response, not inside the chart itself
- do not mimic hospital report layouts
- do not pretend to diagnose

## What to avoid

- no "血脂四项全量折线图" as the default chart
- no dense legend-heavy multi-line charts unless the user explicitly asks
- no unexplained abbreviations as the primary label
- no purple/dark-dashboard style
- no finance-style red-green speculation chart look

## Default visual style

Recommended baseline:
- background: white
- primary accent: medical green
- text: deep neutral gray
- caution: warm amber
- danger: muted red
- support: soft teal

## Minimal design tokens

```json
{
  "color": {
    "bg": "#F8FBF8",
    "surface": "#FFFFFF",
    "text_primary": "#1F2A24",
    "text_secondary": "#5E6C63",
    "accent_medical": "#2F8F6B",
    "accent_soft": "#DFF2EA",
    "line_primary": "#2F8F6B",
    "line_secondary": "#7DB8A3",
    "range_normal": "#DFF2EA",
    "range_caution": "#F6E7B8",
    "range_danger": "#F3C8C1",
    "danger": "#C65A4B",
    "warning": "#B5892E",
    "divider": "#D9E6DE"
  },
  "radius": {
    "card": 18,
    "pill": 999
  },
  "space": {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24
  },
  "type": {
    "title_size": 22,
    "subtitle_size": 15,
    "body_size": 14,
    "caption_size": 12
  },
  "chart": {
    "line_width": 3,
    "point_size": 5,
    "reference_line_width": 2
  }
}
```

## Default display pattern

For most questions, the output should follow this order:

1. plain-language conclusion
2. one focused chart or one simple comparison card
3. supporting recent values
4. source-backed note

## Lipid example rule

When the user asks about blood lipids:
- do not default to one chart containing TC / LDL-C / HDL-C / TG together
- choose one primary metric that best represents the concern
- in v1, prefer `LDL-C` as the default main chart when available
- show the latest other lipid values as supporting text, not as equal-weight lines

Recommended output:
- title: `低密度脂蛋白胆固醇趋势`
- subtitle: `更适合观察血脂风险变化`
- chart: one line only
- supporting facts: latest total cholesterol / triglycerides / HDL-C

## Blood pressure example rule

Blood pressure is one of the few cases where a two-series chart is acceptable:
- systolic
- diastolic

But still keep:
- simple labels
- range guidance
- plain-language explanation below

## Safety wording rule

When the question may influence care-seeking behavior:
- keep the visual simple
- place the risk reminder in text, not only color
- do not let a reassuring-looking chart understate urgent danger
