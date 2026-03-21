# OpenClaw Model Output Guidelines

This file defines how the OpenClaw model should behave before any local archive import happens.

The model's job is not "extract whatever is visible".
The model's job is:
- decide whether the uploaded file is a clearly medical file
- decide whether the file is complete and reliable enough for archive
- if reliable, output one `medical-archive-result/v1` JSON payload
- if unreliable, still output one `medical-archive-result/v1` JSON payload, but with a rejecting `medical_file_gate`

## Primary product rule

Accuracy is more important than recall.

If the file is incomplete, partially blurred, cropped, mixed, or unreliable:
- do not output partial medical observations
- do not guess hidden or unclear values
- do not archive the visible half only
- set `medical_file_gate.decision` to a non-accepted state
- include explicit reject reasons and re-upload guidance
- ask for one complete clear re-upload of the whole report, not extra partial patch images

## The model should reject archive when

- the report as a whole is incomplete or unclear
- the result table is cropped or incomplete
- key report sections are blurred
- multiple different reports are mixed into one image
- multiple different people appear in one upload
- the screenshot only shows part of a report and completeness cannot be confirmed
- the file is not clearly medical

## The model should allow archive only when

- the file is clearly medical
- the report is complete enough to understand as one report unit or a valid PDF split container
- patient identity is readable or strongly clear from the report
- report date is readable or strongly clear from the report
- structured findings can be extracted without obvious guessing

## Output requirements

The model should emit exactly one JSON object using `medical-archive-result/v1`.

Required top-level fields:
- `schema_version`
- `flow`
- `source_file`
- `medical_file_gate`
- `document`
- `observations`

## `medical_file_gate` requirements

Always include:
- `decision`
- `source_kind`

When archive must be rejected or paused, also include:
- `reject_reasons`
- `reupload_advice`

Include these when relevant:
- `missing_sections`
- `quality_flags`
- `reason_code`
- `confidence_label`

Prefer high-level reject reasons such as:
- `incomplete_or_unclear_report`
- `not_clearly_medical`
- `multiple_reports_or_people_detected`

Do not turn the product flow into "please upload one extra name/date corner".
The requested re-upload should be for the whole report.

## Observation extraction rule

If `medical_file_gate.decision` is not `accepted_medical_file`:
- `observations` may stay empty
- or stay minimal
- but the model must not invent a partial final report from incomplete evidence

If `medical_file_gate.decision` is `accepted_medical_file`:
- image/screenshot flow must produce exactly one observation
- PDF split flow may produce multiple observations

## Duplicate-awareness note

The model does not decide final duplicate status.
Local scripts do that.

But the model should still extract these fields carefully because they feed duplicate detection:
- `patient_name`
- `observed_on`
- `report_type`
- `accession_no`

## Style rule for the model

Return JSON only.
Do not wrap in markdown fences.
Do not add explanation before or after the JSON.

## Minimal accepted example

```json
{
  "schema_version": "medical-archive-result/v1",
  "flow": "image_report",
  "source_file": "/absolute/path/to/report.png",
  "medical_file_gate": {
    "decision": "accepted_medical_file",
    "source_kind": "image",
    "reason_code": "complete_clear_medical_report",
    "confidence_label": "high"
  },
  "document": {
    "title": "血脂检验报告",
    "occurred_on": "2026-03-18"
  },
  "observations": [
    {
      "report_type": "lipid panel",
      "title": "血脂检验",
      "observed_on": "2026-03-18",
      "patient_name": "成员A",
      "items": [
        {
          "name": "低密度脂蛋白胆固醇",
          "value": "4.12",
          "unit": "mmol/L"
        }
      ]
    }
  ]
}
```

## Minimal reject example

```json
{
  "schema_version": "medical-archive-result/v1",
  "flow": "image_report",
  "source_file": "/absolute/path/to/partial-report.png",
  "medical_file_gate": {
    "decision": "needs_manual_review",
    "source_kind": "image",
    "reason_code": "incomplete_or_unclear_medical_report",
    "reject_reasons": [
      "incomplete_or_unclear_report"
    ],
    "reupload_advice": "请重新上传完整清晰的原图或原始PDF，确保整张化验单完整可见。"
  },
  "document": {
    "title": "不完整检验报告"
  },
  "observations": []
}
```
