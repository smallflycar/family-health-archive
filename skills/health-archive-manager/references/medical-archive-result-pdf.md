# Medical Archive Result JSON: PDF split flow

This is the manager-side reference payload for a PDF that acts as one source document and produces multiple observation rows.

In v1 product wording, this should be treated as the structured medical archive result produced from the OpenClaw model output and then handed to the local import script.

Use this with:
- `archive_db.py validate-medical-archive-result --json-file ...`
- `archive_db.py import-medical-archive-result --json-file ...`

## Contract

- `schema_version` must be `medical-archive-result/v1`
- `flow` must be `pdf_split_report`
- `medical_file_gate.decision` must be `accepted_medical_file` for import to proceed
- `medical_file_gate.source_kind` must be `pdf`
- `observations` must be a JSON array with one or more independently understandable result units
- all imported observations share the same stored `document_id`
- `person_id` or `person_match` must be provided

## Example

```json
{
  "schema_version": "medical-archive-result/v1",
  "flow": "pdf_split_report",
  "person_id": "11111111-1111-1111-1111-111111111111",
  "person_match": {
    "status": "matched_existing_profile",
    "matched_person_id": "11111111-1111-1111-1111-111111111111",
    "extracted_patient_name": "成员A"
  },
  "source_file": "/absolute/path/to/physical-exam-2026.pdf",
  "medical_file_gate": {
    "stub": false,
    "decision": "accepted_medical_file",
    "reason_code": "physical_exam_pdf_detected",
    "source_kind": "pdf",
    "mime_type": "application/pdf",
    "confidence_label": "high"
  },
  "document": {
    "title": "2026年度体检总报告",
    "occurred_on": "2026-03-10"
  },
  "observations": [
    {
      "report_type": "complete blood count",
      "title": "血常规",
      "observed_on": "2026-03-10",
      "patient_name": "成员A",
      "hospital_name": "示例体检中心",
      "accession_no": "CBC-20260310-01",
      "items": [
        {
          "name": "白细胞计数",
          "value": "5.7",
          "unit": "10^9/L",
          "reference_range": "3.5-9.5"
        }
      ],
      "extra": {
        "pdf_section": "lab/cbc",
        "page_hint": [4, 5]
      }
    },
    {
      "report_type": "thyroid ultrasound",
      "title": "甲状腺超声",
      "observed_on": "2026-03-10",
      "patient_name": "成员A",
      "hospital_name": "示例体检中心",
      "doctor_name": "张医生",
      "items": [
        {
          "name": "超声结论",
          "text": "甲状腺左叶小结节，建议随访"
        }
      ],
      "extra": {
        "pdf_section": "imaging/thyroid_ultrasound",
        "page_hint": [17]
      }
    }
  ]
}
```

## Notes

- This is the default import shape for physical-exam PDFs and similar bundled reports.
- `document` stays lightweight; report-specific semantics belong in each observation.
- For multi-result PDFs, top-level document date can be reused when section-level dates are the same.
- If duplicate checks are enabled, each observation is checked conservatively before the import is finalized.
- If a profile is not matched yet, keep that state in `person_match` and stop before import rather than writing partial archive data.
