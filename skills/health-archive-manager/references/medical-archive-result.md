# Medical Archive Result JSON: `medical-archive-result/v1`

This is the preferred v1 model-output contract for the project.

Product path:
- OpenClaw's current multimodal model reads the uploaded image / screenshot / PDF
- the model outputs one `medical-archive-result/v1` JSON payload
- local scripts validate that payload, resolve `person_match`, detect duplicates, and write SQLite + files

This JSON is a workflow payload, not a separate long-term persisted data layer.
The archive should persist:
- original source files
- SQLite `documents`
- SQLite `observations`

## Required top-level fields

- `schema_version` = `medical-archive-result/v1`
- `flow` = `image_report` or `pdf_split_report`
- `source_file`
- `medical_file_gate`
- `document`
- `observations`

Optional:
- `person_id`
- `person_match`
- in `medical_file_gate`: `reject_reasons`, `missing_sections`, `quality_flags`, `reupload_advice`

## Flow rules

- `image_report` -> exactly one observation
- `pdf_split_report` -> one or more observations
- unresolved `person_match` may validate, but import must stop before writing

## Manager-side commands

- `archive_db.py validate-medical-archive-result --json-file ...`
- `archive_db.py process-medical-archive-result --json-file ...`
- `archive_db.py resolve-medical-archive-result-person --json-file ...`
- `archive_db.py assign-person-to-medical-archive-result --json-file ... --person-id ...`
- `archive_db.py create-person-for-medical-archive-result --json-file ... [--name ...]`
- `archive_db.py import-medical-archive-result --json-file ...`

## Shape notes

The payload shape intentionally stays close to the archive semantics:
- `document` describes the original uploaded file
- `observations` describes one or more independently understandable medical result units
- `items` contains structured metrics / findings
- `extra` holds uncommon report-specific fields

For conservative archive quality control:
- if the file is partially blurred, cropped, incomplete, or identity/date is unclear, the model should set `medical_file_gate.decision` to a non-accepted state
- use `reject_reasons` to explain why the file must not be archived
- use `missing_sections` and `quality_flags` to describe what is incomplete/unclear
- use `reupload_advice` to tell the user what kind of new upload is needed

Use the existing flow-specific references for concrete examples:
- `medical-archive-result-image.md`
- `medical-archive-result-pdf.md`
