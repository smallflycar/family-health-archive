# Medical Archive Result JSON: image/screenshot flow

This is the manager-side reference payload for a single medical image or screenshot that should archive as one observation.

In v1 product wording, this should be treated as the structured medical archive result produced from the OpenClaw model output and then handed to the local import script.

Use this with:
- `archive_db.py validate-medical-archive-result --json-file ...`
- `archive_db.py import-medical-archive-result --json-file ...`

## Contract

- `schema_version` must be `medical-archive-result/v1`
- `flow` must be `image_report`
- `medical_file_gate.decision` must be `accepted_medical_file` for import to proceed
- `medical_file_gate.source_kind` must be `image` or `screenshot`
- `observations` must contain exactly one observation
- `person_id` or `person_match` must be provided

## Example

```json
{
  "schema_version": "medical-archive-result/v1",
  "flow": "image_report",
  "person_id": "11111111-1111-1111-1111-111111111111",
  "person_match": {
    "status": "matched_existing_profile",
    "matched_person_id": "11111111-1111-1111-1111-111111111111",
    "extracted_patient_name": "成员A"
  },
  "source_file": "/absolute/path/to/lipid-report.png",
  "medical_file_gate": {
    "stub": false,
    "decision": "accepted_medical_file",
    "reason_code": "multimodal_medical_report_detected",
    "source_kind": "screenshot",
    "mime_type": "image/png",
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
      "patient_sex": "女",
      "patient_age_text": "68岁",
      "hospital_name": "示例医院",
      "department_name": "检验科",
      "specimen_type": "血清",
      "accession_no": "LIPID-20260318-01",
      "items": [
        {
          "name": "总胆固醇",
          "value": "6.20",
          "unit": "mmol/L",
          "reference_range": "0-5.20",
          "flag": "↑"
        },
        {
          "name": "高密度脂蛋白胆固醇",
          "value": "1.33",
          "unit": "mmol/L",
          "reference_range": "1.04-1.55"
        }
      ],
      "extra": {
        "extraction_notes": "single screenshot import"
      }
    }
  ]
}
```

## Notes

- `document.occurred_on` should usually match the observation date when the image contains one report.
- `items` maps to `observations.items_json`.
- `extra` maps to `observations.extra_json`.
- If the gate decision is `rejected_not_medical`, the importer returns `not_imported` with `reason=not_medical_file`.
- If the gate decision is `needs_manual_review`, the importer returns `not_imported` with `reason=needs_manual_review_before_import`.
- If `person_match.status` is not `matched_existing_profile`, the importer returns `not_imported` with `reason=person_profile_action_required`.
