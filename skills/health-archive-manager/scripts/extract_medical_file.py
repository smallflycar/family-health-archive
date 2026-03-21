#!/usr/bin/env python3
"""Local bridge for one medical file and one model-produced medical archive result JSON."""

from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path

from archive_db import (
    connect,
    ensure_data_root,
    fail,
    get_person,
    init_db,
    json_dumps,
    match_person_by_name,
    resolve_data_root,
    validate_extraction_payload,
)
from archive_db import load_json_file


def infer_source_kind_from_file(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    suffix = path.suffix.lower()
    lowered_name = path.name.lower()

    if mime.startswith("image/"):
        if "screenshot" in lowered_name or "screen" in lowered_name:
            return "screenshot"
        return "image"
    if mime == "application/pdf" or suffix == ".pdf":
        return "pdf"
    raise ValueError(f"unsupported file type for extraction: {path.name}")


def resolve_person_match(conn, extraction_result: dict, explicit_person_id: str | None) -> dict:
    if explicit_person_id:
        person = get_person(conn, explicit_person_id)
        if not person:
            raise ValueError(f"person_id does not exist: {explicit_person_id}")
        extraction_result["person_id"] = explicit_person_id
        extraction_result["person_match"] = {
            "status": "matched_existing_profile",
            "matched_person_id": explicit_person_id,
            "candidate_person_ids": [],
            "extracted_patient_name": extraction_result["observations"][0]["patient_name"],
            "notes": "Profile was provided explicitly by caller",
        }
        return validate_extraction_payload(extraction_result)

    existing_person_id = extraction_result.get("person_id")
    if existing_person_id:
        person = get_person(conn, existing_person_id)
        if not person:
            raise ValueError(f"person_id does not exist: {existing_person_id}")
        return validate_extraction_payload(extraction_result)

    person_match = extraction_result.get("person_match") or {}
    matched_person_id = person_match.get("matched_person_id")
    if person_match.get("status") == "matched_existing_profile" and matched_person_id:
        person = get_person(conn, matched_person_id)
        if not person:
            raise ValueError(f"matched person does not exist: {matched_person_id}")
        extraction_result["person_id"] = matched_person_id
        return validate_extraction_payload(extraction_result)

    extracted_patient_name = (
        person_match.get("extracted_patient_name")
        or extraction_result["observations"][0]["patient_name"]
    )
    resolved_match = match_person_by_name(conn, extracted_patient_name)
    extraction_result["person_id"] = (
        resolved_match["matched_person_id"]
        if resolved_match["status"] == "matched_existing_profile"
        else None
    )
    extraction_result["person_match"] = resolved_match
    return validate_extraction_payload(extraction_result)


def load_model_result_payload(args, source_file: Path, source_kind: str) -> dict:
    payload = load_json_file(Path(args.json_file))
    if payload.get("schema_version") and payload.get("person_id") is None and payload.get("person_match") is None:
        observations = payload.get("observations")
        extracted_patient_name = None
        if isinstance(observations, list) and observations and isinstance(observations[0], dict):
            extracted_patient_name = observations[0].get("patient_name")
        payload = dict(payload)
        payload["person_match"] = {
            "status": "needs_profile_creation",
            "extracted_patient_name": extracted_patient_name,
            "notes": "Profile resolution is handled locally after model output",
        }
    return validate_extraction_payload(payload)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", help="Archive data root. Defaults to FAMILY_HEALTH_DATA_DIR or ~/.family-health-data")
    parser.add_argument("--file", required=True, help="Local source image/screenshot/PDF to extract")
    parser.add_argument("--json-file", required=True, help="One model-produced medical archive result JSON")
    parser.add_argument("--person-id", help="Force archive under an existing profile")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    source_file = Path(args.file).expanduser().resolve()
    if not source_file.exists():
        return fail(
            f"file does not exist: {source_file}",
            code="file_missing",
            details={"file": str(source_file)},
        )

    try:
        source_kind = infer_source_kind_from_file(source_file)
        data_root = resolve_data_root(args.data_root)
        db_path, _files_root = ensure_data_root(data_root)
        conn = connect(db_path)
        init_db(conn)

        extraction_result = load_model_result_payload(args, source_file, source_kind)
        if Path(extraction_result["source_file"]).expanduser().resolve() != source_file:
            raise ValueError("model result JSON source_file does not match --file")

        resolved_result = resolve_person_match(conn, extraction_result, args.person_id)
    except (OSError, ValueError) as exc:
        return fail(
            str(exc),
            code="extract_medical_file_failed",
            details={"file": str(source_file), "json_file": args.json_file},
        )

    if args.pretty:
        import json
        print(json.dumps(resolved_result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json_dumps(resolved_result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
