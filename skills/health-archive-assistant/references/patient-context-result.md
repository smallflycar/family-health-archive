# Patient Context Result JSON: `patient-context-result/v1`

This is the assistant-side readable fact-organization layer for one person.

Purpose:
- reorganize archived structured facts into a more readable patient context
- support later model reasoning, human review, follow-up prep, and risk reminders
- improve readability without pretending to replace diagnosis

This layer does not try to decide final medical meaning.
It only groups and surfaces evidence-backed facts.

## Required top-level fields

- `schema_version` = `patient-context-result/v1`
- `person`
- `recent_reports`
- `recent_trend_data`
- `history_candidates`
- `source_refs`

## `person`

Profile basics for the target archive person.

## `recent_reports`

A short list of recent archived reports.

Expected fields per item:
- `observation_id`
- `observed_on`
- `report_type`
- `title`
- `hospital_name`
- `patient_name`
- `source_doc_id`

## `recent_trend_data`

Zero or more domain analysis payloads that are useful for trend-style questions.

Recommended starting domains:
- `lipids`
- `glucose`
- `blood_pressure`
- `weight`

## `history_candidates`

Long-term history candidates extracted conservatively from archived reports.

These are not final diagnoses.
They are evidence-backed candidate history entries surfaced for later model analysis and human review.

Expected fields per item:
- `category`
- `observed_on`
- `report_type`
- `title`
- `summary_text`
- `source_observation_id`
- `source_doc_id`

## `source_refs`

Source references for later trace-back to structured rows and original files.

Expected fields per item:
- `observation_id`
- `source_doc_id`
- `observed_on`
- `report_type`
- `title`
- `file_relpath`

## Initial implementation scope

The first implementation only needs a conservative readable context:
- profile basics
- recent reports
- recent trend data for a few fixed domains
- text-like history candidates from report items / titles / report types
- source references
