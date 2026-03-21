#!/usr/bin/env python3
"""Shared family health archive SQLite helper.

Design goals:
- No daemon. Single-file SQLite.
- Code directory and data directory are separate.
- Shared schema for multiple first-party / third-party skills.
- Lightweight documents table + structured observation units.

Default data root:
- Linux/macOS: ~/.family-health-data
- Windows: %USERPROFILE%\\.family-health-data
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import mimetypes
import os
import shutil
import sqlite3
import sys
import time
import uuid
from pathlib import Path

SCHEMA_VERSION = 2
MEDICAL_ARCHIVE_RESULT_SCHEMA_VERSION = "medical-archive-result/v1"
SUPPORTED_IMPORT_SCHEMA_VERSIONS = {MEDICAL_ARCHIVE_RESULT_SCHEMA_VERSION}
SUPPORTED_IMPORT_FLOWS = {"image_report", "pdf_split_report"}
SUPPORTED_GATE_DECISIONS = {"accepted_medical_file", "rejected_not_medical", "needs_manual_review"}
SUPPORTED_SOURCE_KINDS = {"image", "screenshot", "pdf"}
SUPPORTED_PERSON_MATCH_STATUSES = {
    "matched_existing_profile",
    "needs_profile_selection",
    "needs_profile_creation",
}
SUPPORTED_RELATIONSHIP_TYPES = {
    "mother_of",
    "father_of",
    "daughter_of",
    "son_of",
    "spouse_of",
}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def default_data_root() -> Path:
    home = Path.home()
    return home / ".family-health-data"


def resolve_data_root(cli_value: str | None) -> Path:
    if cli_value:
        return Path(cli_value).expanduser().resolve()
    env = os.environ.get("FAMILY_HEALTH_DATA_DIR")
    if env:
        return Path(env).expanduser().resolve()
    return default_data_root().resolve()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def json_dumps(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def fail(message: str, *, code: str, details: dict | None = None, exit_code: int = 2) -> int:
    payload = {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details:
        payload["error"]["details"] = details
    print(json_dumps(payload))
    return exit_code


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        pass
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta(
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS people(
          id TEXT PRIMARY KEY,
          display_name TEXT NOT NULL,
          aliases_json TEXT,
          sex TEXT,
          dob TEXT,
          height_cm REAL,
          current_weight_kg REAL,
          notes TEXT,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_people_display_name
          ON people(display_name);

        CREATE TABLE IF NOT EXISTS documents(
          id TEXT PRIMARY KEY,
          person_id TEXT NOT NULL REFERENCES people(id),
          title TEXT,
          occurred_on TEXT,
          file_relpath TEXT NOT NULL,
          sha256 TEXT NOT NULL UNIQUE,
          mime_type TEXT,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_documents_person_date
          ON documents(person_id, occurred_on);

        CREATE TABLE IF NOT EXISTS observations(
          id TEXT PRIMARY KEY,
          person_id TEXT NOT NULL REFERENCES people(id),
          source_doc_id TEXT NOT NULL REFERENCES documents(id),
          report_type TEXT NOT NULL,
          title TEXT,
          observed_on TEXT,
          patient_name TEXT,
          patient_sex TEXT,
          patient_age_text TEXT,
          patient_dob TEXT,
          hospital_name TEXT,
          department_name TEXT,
          doctor_name TEXT,
          specimen_type TEXT,
          accession_no TEXT,
          items_json TEXT NOT NULL,
          extra_json TEXT,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_observations_person_date
          ON observations(person_id, observed_on);

        CREATE INDEX IF NOT EXISTS idx_observations_source_doc
          ON observations(source_doc_id);

        CREATE INDEX IF NOT EXISTS idx_observations_report_type
          ON observations(report_type);

        CREATE TABLE IF NOT EXISTS tags(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS document_tags(
          document_id TEXT REFERENCES documents(id),
          tag_id INTEGER REFERENCES tags(id),
          PRIMARY KEY(document_id, tag_id)
        );

        CREATE TABLE IF NOT EXISTS person_relationships(
          id TEXT PRIMARY KEY,
          subject_person_id TEXT NOT NULL REFERENCES people(id),
          relation_type TEXT NOT NULL,
          object_person_id TEXT NOT NULL REFERENCES people(id),
          notes TEXT,
          created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_person_relationships_subject
          ON person_relationships(subject_person_id);

        CREATE INDEX IF NOT EXISTS idx_person_relationships_object
          ON person_relationships(object_person_id);
        """
    )

    conn.execute(
        "INSERT OR REPLACE INTO meta(key,value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def _retry_write(fn, attempts: int = 5, base_sleep: float = 0.15):
    last = None
    for i in range(attempts):
        try:
            return fn()
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if "locked" in msg or "busy" in msg:
                last = e
                time.sleep(base_sleep * (2**i))
                continue
            raise
    raise sqlite3.OperationalError(
        "SQLite is busy (another archive write may be running). Please retry in a few seconds."
    ) from last


def ensure_data_root(data_root: Path) -> tuple[Path, Path]:
    data_root.mkdir(parents=True, exist_ok=True)
    files_root = data_root / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    db_path = data_root / "archive.db"
    return db_path, files_root


def add_person(
    conn: sqlite3.Connection,
    display_name: str,
    aliases: list[str] | None,
    sex: str | None,
    dob: str | None,
    height_cm: float | None,
    current_weight_kg: float | None,
    notes: str | None,
) -> str:
    pid = str(uuid.uuid4())

    def _op():
        conn.execute(
            """
            INSERT INTO people(
              id, display_name, aliases_json, sex, dob,
              height_cm, current_weight_kg, notes, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                pid,
                display_name,
                json.dumps(aliases or [], ensure_ascii=False),
                sex,
                dob,
                height_cm,
                current_weight_kg,
                notes,
                iso_now(),
            ),
        )

    _retry_write(_op)
    return pid


def list_people(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM people ORDER BY created_at DESC")
    return list(cur.fetchall())


def add_relationship(
    conn: sqlite3.Connection,
    subject_person_id: str,
    relation_type: str,
    object_person_id: str,
    notes: str | None,
) -> str:
    if relation_type not in SUPPORTED_RELATIONSHIP_TYPES:
        raise ValueError(
            "relation_type must be one of: " + ", ".join(sorted(SUPPORTED_RELATIONSHIP_TYPES))
        )
    if not get_person(conn, subject_person_id):
        raise ValueError(f"subject_person_id does not exist: {subject_person_id}")
    if not get_person(conn, object_person_id):
        raise ValueError(f"object_person_id does not exist: {object_person_id}")

    existing = conn.execute(
        """
        SELECT id FROM person_relationships
        WHERE subject_person_id=? AND relation_type=? AND object_person_id=?
        """,
        (subject_person_id, relation_type, object_person_id),
    ).fetchone()
    if existing:
        return str(existing["id"])

    rid = str(uuid.uuid4())

    def _op():
        conn.execute(
            """
            INSERT INTO person_relationships(
              id, subject_person_id, relation_type, object_person_id, notes, created_at
            ) VALUES(?,?,?,?,?,?)
            """,
            (
                rid,
                subject_person_id,
                relation_type,
                object_person_id,
                notes,
                iso_now(),
            ),
        )

    _retry_write(_op)
    return rid


def list_relationships(conn: sqlite3.Connection, person_id: str | None = None) -> list[sqlite3.Row]:
    if person_id:
        cur = conn.execute(
            """
            SELECT * FROM person_relationships
            WHERE subject_person_id=? OR object_person_id=?
            ORDER BY created_at DESC
            """,
            (person_id, person_id),
        )
    else:
        cur = conn.execute(
            "SELECT * FROM person_relationships ORDER BY created_at DESC"
        )
    return list(cur.fetchall())


def find_people(conn: sqlite3.Connection, q: str) -> list[sqlite3.Row]:
    q_like = f"%{q}%"
    cur = conn.execute(
        """
        SELECT * FROM people
        WHERE display_name LIKE ?
           OR aliases_json LIKE ?
        ORDER BY created_at DESC
        """,
        (q_like, q_like),
    )
    return list(cur.fetchall())


def get_person(conn: sqlite3.Connection, person_id: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()


def person_summary(row: sqlite3.Row) -> dict:
    try:
        aliases = json.loads(row["aliases_json"] or "[]")
    except json.JSONDecodeError:
        aliases = []
    return {
        "id": row["id"],
        "display_name": row["display_name"],
        "aliases": aliases,
        "sex": row["sex"],
        "dob": row["dob"],
    }


def normalize_person_name(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.casefold() if not ch.isspace())


def match_person_by_name(conn: sqlite3.Connection, extracted_patient_name: str | None) -> dict:
    normalized_name = normalize_person_name(extracted_patient_name)
    if not normalized_name:
        return {
            "status": "needs_profile_creation",
            "matched_person_id": None,
            "candidate_person_ids": [],
            "extracted_patient_name": extracted_patient_name,
            "notes": "No reliable patient name was extracted from the file",
        }

    rows = list_people(conn)
    exact_display_matches = []
    exact_alias_matches = []

    for row in rows:
        if normalize_person_name(row["display_name"]) == normalized_name:
            exact_display_matches.append(row)
            continue

        aliases = []
        try:
            aliases = json.loads(row["aliases_json"] or "[]")
        except json.JSONDecodeError:
            aliases = []

        if any(normalize_person_name(alias) == normalized_name for alias in aliases if isinstance(alias, str)):
            exact_alias_matches.append(row)

    preferred_matches = exact_display_matches or exact_alias_matches

    if len(preferred_matches) == 1:
        return {
            "status": "matched_existing_profile",
            "matched_person_id": preferred_matches[0]["id"],
            "candidate_person_ids": [],
            "extracted_patient_name": extracted_patient_name,
            "notes": "Matched by exact profile name" if exact_display_matches else "Matched by exact alias",
        }

    if len(preferred_matches) > 1:
        return {
            "status": "needs_profile_selection",
            "matched_person_id": None,
            "candidate_person_ids": [row["id"] for row in preferred_matches],
            "extracted_patient_name": extracted_patient_name,
            "notes": "Multiple existing profiles matched the extracted patient name",
        }

    return {
        "status": "needs_profile_creation",
        "matched_person_id": None,
        "candidate_person_ids": [],
        "extracted_patient_name": extracted_patient_name,
        "notes": "No existing profile matched the extracted patient name",
    }


def list_documents(conn: sqlite3.Connection, person_id: str | None = None) -> list[sqlite3.Row]:
    if person_id:
        cur = conn.execute(
            "SELECT * FROM documents WHERE person_id=? ORDER BY occurred_on DESC, created_at DESC",
            (person_id,),
        )
    else:
        cur = conn.execute("SELECT * FROM documents ORDER BY occurred_on DESC, created_at DESC")
    return list(cur.fetchall())


def list_observations(conn: sqlite3.Connection, person_id: str | None = None) -> list[sqlite3.Row]:
    if person_id:
        cur = conn.execute(
            "SELECT * FROM observations WHERE person_id=? ORDER BY observed_on DESC, created_at DESC",
            (person_id,),
        )
    else:
        cur = conn.execute("SELECT * FROM observations ORDER BY observed_on DESC, created_at DESC")
    return list(cur.fetchall())


def normalize_items_for_compare(items: list) -> str:
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        normalized.append({k: item[k] for k in sorted(item.keys())})
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def observation_summary(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "person_id": row["person_id"],
        "report_type": row["report_type"],
        "title": row["title"],
        "observed_on": row["observed_on"],
        "patient_name": row["patient_name"],
        "hospital_name": row["hospital_name"],
        "accession_no": row["accession_no"],
    }


def observation_items(row: sqlite3.Row) -> list:
    try:
        return json.loads(row["items_json"] or "[]")
    except Exception:
        return []


def infer_gate_stub(path: Path) -> dict:
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    suffix = path.suffix.lower()
    lowered_name = path.name.lower()

    filename_signals = [
        token
        for token in (
            "lab",
            "report",
            "medical",
            "hospital",
            "exam",
            "checkup",
            "cbc",
            "lipid",
            "glucose",
            "ultrasound",
            "ecg",
            "ct",
            "mri",
            "xray",
            "检验",
            "化验",
            "体检",
            "医院",
            "报告",
            "血常规",
            "血脂",
            "超声",
            "心电",
        )
        if token in lowered_name
    ]

    if mime.startswith("image/"):
        source_kind = "screenshot" if "screenshot" in lowered_name or "screen" in lowered_name else "image"
    elif mime == "application/pdf" or suffix == ".pdf":
        source_kind = "pdf"
    else:
        source_kind = "unknown"

    if source_kind == "unknown":
        decision = "rejected_not_medical"
        reason_code = "unsupported_file_type"
    elif filename_signals:
        decision = "accepted_medical_file"
        reason_code = "filename_medical_signal"
    else:
        decision = "needs_manual_review"
        reason_code = "stub_requires_medical_classifier"

    return {
        "stub": True,
        "decision": decision,
        "reason_code": reason_code,
        "source_kind": source_kind,
        "mime_type": mime,
        "filename_signals": filename_signals,
        "supported_for_ingest": source_kind in SUPPORTED_SOURCE_KINDS,
    }


def require_object(value, field_name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return value


def require_list(value, field_name: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array")
    return value


def optional_str(value, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string when provided")
    return value


def optional_str_list(value, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON array when provided")
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        result.append(item)
    return result


def nonempty_optional_str_list(value, field_name: str) -> list[str]:
    result = optional_str_list(value, field_name)
    return [item for item in result if item]


def normalize_observation_input(observation: dict, index: int) -> dict:
    require_object(observation, f"observations[{index}]")

    report_type = optional_str(observation.get("report_type"), f"observations[{index}].report_type")
    if not report_type:
        raise ValueError(f"observations[{index}].report_type is required")

    items = require_list(observation.get("items"), f"observations[{index}].items")

    extra = observation.get("extra")
    if extra is None:
        extra = {}
    extra = require_object(extra, f"observations[{index}].extra")

    return {
        "report_type": report_type,
        "title": optional_str(observation.get("title"), f"observations[{index}].title"),
        "observed_on": optional_str(observation.get("observed_on"), f"observations[{index}].observed_on"),
        "patient_name": optional_str(observation.get("patient_name"), f"observations[{index}].patient_name"),
        "patient_sex": optional_str(observation.get("patient_sex"), f"observations[{index}].patient_sex"),
        "patient_age_text": optional_str(
            observation.get("patient_age_text"), f"observations[{index}].patient_age_text"
        ),
        "patient_dob": optional_str(observation.get("patient_dob"), f"observations[{index}].patient_dob"),
        "hospital_name": optional_str(observation.get("hospital_name"), f"observations[{index}].hospital_name"),
        "department_name": optional_str(
            observation.get("department_name"), f"observations[{index}].department_name"
        ),
        "doctor_name": optional_str(observation.get("doctor_name"), f"observations[{index}].doctor_name"),
        "specimen_type": optional_str(
            observation.get("specimen_type"), f"observations[{index}].specimen_type"
        ),
        "accession_no": optional_str(observation.get("accession_no"), f"observations[{index}].accession_no"),
        "items": items,
        "extra": extra,
    }


def normalize_medical_file_gate(gate: dict) -> dict:
    require_object(gate, "medical_file_gate")

    decision = optional_str(gate.get("decision"), "medical_file_gate.decision")
    if decision not in SUPPORTED_GATE_DECISIONS:
        raise ValueError(
            "medical_file_gate.decision must be one of: "
            + ", ".join(sorted(SUPPORTED_GATE_DECISIONS))
        )

    source_kind = optional_str(gate.get("source_kind"), "medical_file_gate.source_kind")
    if source_kind not in SUPPORTED_SOURCE_KINDS:
        raise ValueError(
            "medical_file_gate.source_kind must be one of: "
            + ", ".join(sorted(SUPPORTED_SOURCE_KINDS))
        )

    reject_reasons = nonempty_optional_str_list(
        gate.get("reject_reasons"), "medical_file_gate.reject_reasons"
    )
    missing_sections = nonempty_optional_str_list(
        gate.get("missing_sections"), "medical_file_gate.missing_sections"
    )
    quality_flags = nonempty_optional_str_list(
        gate.get("quality_flags"), "medical_file_gate.quality_flags"
    )
    reupload_advice = optional_str(gate.get("reupload_advice"), "medical_file_gate.reupload_advice")

    if decision != "accepted_medical_file":
        if not reject_reasons:
            raise ValueError("medical_file_gate.reject_reasons is required when decision is not accepted_medical_file")
        if not reupload_advice and decision == "needs_manual_review":
            raise ValueError("medical_file_gate.reupload_advice is required for needs_manual_review")

    return {
        "stub": bool(gate.get("stub", False)),
        "decision": decision,
        "reason_code": optional_str(gate.get("reason_code"), "medical_file_gate.reason_code"),
        "source_kind": source_kind,
        "mime_type": optional_str(gate.get("mime_type"), "medical_file_gate.mime_type"),
        "confidence_label": optional_str(
            gate.get("confidence_label"), "medical_file_gate.confidence_label"
        ),
        "notes": optional_str(gate.get("notes"), "medical_file_gate.notes"),
        "reject_reasons": reject_reasons,
        "missing_sections": missing_sections,
        "quality_flags": quality_flags,
        "reupload_advice": reupload_advice,
    }


def import_blocked_result(reason: str, gate: dict | None = None, person_match: dict | None = None) -> dict:
    result = {
        "status": "not_imported",
        "reason": reason,
    }
    if gate is not None:
        result["medical_file_gate"] = gate
        result["next_action"] = "reupload_file" if gate["decision"] != "accepted_medical_file" else "resolve_person"
        result["reject_reasons"] = gate.get("reject_reasons", [])
        result["missing_sections"] = gate.get("missing_sections", [])
        result["quality_flags"] = gate.get("quality_flags", [])
        if gate.get("reupload_advice"):
            result["reupload_advice"] = gate["reupload_advice"]
    if person_match is not None:
        result["person_match"] = person_match
        if person_match["status"] != "matched_existing_profile":
            result["next_action"] = "resolve_person_profile"
    return result


def validate_extraction_payload(payload: dict) -> dict:
    require_object(payload, "payload")

    schema_version = optional_str(payload.get("schema_version"), "schema_version")
    if schema_version not in SUPPORTED_IMPORT_SCHEMA_VERSIONS:
        raise ValueError(
            "schema_version must be one of: "
            + ", ".join(sorted(SUPPORTED_IMPORT_SCHEMA_VERSIONS))
        )

    flow = optional_str(payload.get("flow"), "flow")
    if flow not in SUPPORTED_IMPORT_FLOWS:
        raise ValueError(f"flow must be one of: {', '.join(sorted(SUPPORTED_IMPORT_FLOWS))}")

    person_id = optional_str(payload.get("person_id"), "person_id")

    source_file = optional_str(payload.get("source_file"), "source_file")
    if not source_file:
        raise ValueError("source_file is required")

    gate = normalize_medical_file_gate(payload.get("medical_file_gate"))
    decision = gate["decision"]
    source_kind = gate["source_kind"]

    if flow == "pdf_split_report" and source_kind != "pdf":
        raise ValueError("pdf_split_report requires medical_file_gate.source_kind=pdf")

    if flow == "image_report" and source_kind not in {"image", "screenshot"}:
        raise ValueError("image_report requires medical_file_gate.source_kind=image or screenshot")

    document = require_object(payload.get("document"), "document")
    title = optional_str(document.get("title"), "document.title")
    occurred_on = optional_str(document.get("occurred_on"), "document.occurred_on")

    observations_input = require_list(payload.get("observations"), "observations")
    observations = [
        normalize_observation_input(observation, index)
        for index, observation in enumerate(observations_input)
    ]
    if not observations:
        raise ValueError("observations must contain at least one result")
    if flow == "image_report" and len(observations) != 1:
        raise ValueError("image_report must contain exactly one observation")

    person_match_input = payload.get("person_match")
    if person_match_input is None:
        if not person_id:
            raise ValueError("person_id is required unless person_match is provided")
        person_match = {
            "status": "matched_existing_profile",
            "matched_person_id": person_id,
            "candidate_person_ids": [],
            "extracted_patient_name": observations[0]["patient_name"],
            "notes": None,
        }
    else:
        person_match_raw = require_object(person_match_input, "person_match")
        status = optional_str(person_match_raw.get("status"), "person_match.status")
        if status not in SUPPORTED_PERSON_MATCH_STATUSES:
            raise ValueError(
                "person_match.status must be one of: "
                + ", ".join(sorted(SUPPORTED_PERSON_MATCH_STATUSES))
            )
        matched_person_id = optional_str(
            person_match_raw.get("matched_person_id"), "person_match.matched_person_id"
        )
        candidate_person_ids = optional_str_list(
            person_match_raw.get("candidate_person_ids"), "person_match.candidate_person_ids"
        )
        if status == "matched_existing_profile":
            matched_person_id = matched_person_id or person_id
            if not matched_person_id:
                raise ValueError("matched_existing_profile requires person_match.matched_person_id or person_id")
        else:
            if person_id and matched_person_id and person_id != matched_person_id:
                raise ValueError("person_id must match person_match.matched_person_id when both are provided")
            if person_id and not matched_person_id:
                matched_person_id = person_id
        person_match = {
            "status": status,
            "matched_person_id": matched_person_id,
            "candidate_person_ids": candidate_person_ids,
            "extracted_patient_name": optional_str(
                person_match_raw.get("extracted_patient_name"), "person_match.extracted_patient_name"
            ) or observations[0]["patient_name"],
            "notes": optional_str(person_match_raw.get("notes"), "person_match.notes"),
        }

    validated_person_id = person_match["matched_person_id"] if person_match["status"] == "matched_existing_profile" else None

    return {
        "schema_version": schema_version,
        "flow": flow,
        "person_id": validated_person_id,
        "person_match": person_match,
        "source_file": source_file,
        "medical_file_gate": gate,
        "document": {
            "title": title,
            "occurred_on": occurred_on,
        },
        "observations": observations,
        "ingest_plan": {
            "document_scope": "single_report_document" if flow == "image_report" else "container_document",
            "observation_count": len(observations),
            "profile_required": True,
        },
    }


def extracted_patient_name_from_payload(validated_payload: dict) -> str | None:
    return (
        validated_payload["person_match"].get("extracted_patient_name")
        or validated_payload["observations"][0]["patient_name"]
    )


def resolved_payload_with_person_match(payload: dict, person_match: dict) -> dict:
    updated_payload = dict(payload)
    updated_payload["person_match"] = person_match
    updated_payload["person_id"] = (
        person_match["matched_person_id"]
        if person_match["status"] == "matched_existing_profile"
        else None
    )
    return validate_extraction_payload(updated_payload)


def resolve_person_match_for_payload(conn: sqlite3.Connection, payload: dict) -> dict:
    validated = validate_extraction_payload(payload)
    person_match = validated["person_match"]

    if person_match["status"] == "matched_existing_profile" and validated["person_id"]:
        person = get_person(conn, validated["person_id"])
        if not person:
            raise ValueError(f"matched person does not exist: {validated['person_id']}")
        return validated

    resolved_match = match_person_by_name(conn, extracted_patient_name_from_payload(validated))
    return resolved_payload_with_person_match(validated, resolved_match)


def candidate_people_for_match(conn: sqlite3.Connection, person_match: dict) -> list[dict]:
    result = []
    for person_id in person_match.get("candidate_person_ids", []):
        row = get_person(conn, person_id)
        if row:
            result.append(person_summary(row))
    return result


def assign_person_to_payload(conn: sqlite3.Connection, payload: dict, person_id: str) -> dict:
    row = get_person(conn, person_id)
    if not row:
        raise ValueError(f"person_id does not exist: {person_id}")

    validated = validate_extraction_payload(payload)
    assigned_match = {
        "status": "matched_existing_profile",
        "matched_person_id": person_id,
        "candidate_person_ids": [],
        "extracted_patient_name": extracted_patient_name_from_payload(validated),
        "notes": "Person was selected explicitly during archive workflow",
    }
    return resolved_payload_with_person_match(validated, assigned_match)


def create_person_for_payload(
    conn: sqlite3.Connection,
    payload: dict,
    *,
    name: str | None,
    aliases: list[str],
    sex: str | None,
    dob: str | None,
    height_cm: float | None,
    current_weight_kg: float | None,
    notes: str | None,
) -> tuple[str, dict]:
    validated = validate_extraction_payload(payload)
    extracted_name = extracted_patient_name_from_payload(validated)
    observation = validated["observations"][0]

    display_name = name or extracted_name
    if not display_name:
        raise ValueError("--name is required when the payload does not contain an extracted patient name")

    merged_aliases = list(aliases)
    if extracted_name and extracted_name != display_name and extracted_name not in merged_aliases:
        merged_aliases.append(extracted_name)

    pid = add_person(
        conn,
        display_name=display_name,
        aliases=merged_aliases,
        sex=sex or observation["patient_sex"],
        dob=dob or observation["patient_dob"],
        height_cm=height_cm,
        current_weight_kg=current_weight_kg,
        notes=notes,
    )
    return pid, assign_person_to_payload(conn, validated, pid)


def import_extraction_payload(
    conn: sqlite3.Connection,
    files_root: Path,
    payload: dict,
    *,
    check_soft_duplicate: bool,
) -> tuple[int, dict]:
    validated = validate_extraction_payload(payload)

    gate = validated["medical_file_gate"]
    if gate["decision"] != "accepted_medical_file":
        reason = {
            "rejected_not_medical": "not_medical_file",
            "needs_manual_review": "needs_manual_review_before_import",
        }.get(gate["decision"], "medical_file_gate_rejected")
        return 20, import_blocked_result(reason, gate=gate)

    person_match = validated["person_match"]
    if person_match["status"] != "matched_existing_profile" or not validated["person_id"]:
        return 21, import_blocked_result(
            "person_profile_action_required",
            gate=gate,
            person_match=person_match,
        )

    source_path = Path(validated["source_file"]).expanduser().resolve()
    if not source_path.exists():
        return 2, {
            "status": "error",
            "error": {
                "code": "source_file_missing",
                "message": f"source file does not exist: {source_path}",
            },
        }

    document_title = validated["document"]["title"] or source_path.name
    document_date = validated["document"]["occurred_on"] or validated["observations"][0]["observed_on"]

    did = add_document(
        conn,
        files_root=files_root,
        src=source_path,
        person_id=validated["person_id"],
        title=document_title,
        occurred_on=document_date,
    )

    duplicate_groups = []
    if check_soft_duplicate:
        for observation in validated["observations"]:
            rows = soft_duplicate_candidates(
                conn,
                person_id=validated["person_id"],
                report_type=observation["report_type"],
                observed_on=observation["observed_on"],
                accession_no=observation["accession_no"],
                items=observation["items"],
            )
            if rows:
                duplicate_groups.append(
                    {
                        "report_type": observation["report_type"],
                        "title": observation["title"],
                        "observed_on": observation["observed_on"],
                        "existing": [
                            {
                                "summary": observation_summary(row),
                                "items": observation_items(row),
                            }
                            for row in rows
                        ],
                    }
                )

    if duplicate_groups:
        return 10, {
            "status": "suspected_duplicate",
            "document_id": did,
            "flow": validated["flow"],
            "duplicates": duplicate_groups,
        }

    observation_ids = []
    for observation in validated["observations"]:
        oid = add_observation(
            conn,
            person_id=validated["person_id"],
            source_doc_id=did,
            report_type=observation["report_type"],
            title=observation["title"],
            observed_on=observation["observed_on"],
            patient_name=observation["patient_name"],
            patient_sex=observation["patient_sex"],
            patient_age_text=observation["patient_age_text"],
            patient_dob=observation["patient_dob"],
            hospital_name=observation["hospital_name"],
            department_name=observation["department_name"],
            doctor_name=observation["doctor_name"],
            specimen_type=observation["specimen_type"],
            accession_no=observation["accession_no"],
            items=observation["items"],
            extra=observation["extra"],
        )
        observation_ids.append(oid)

    return 0, {
        "status": "imported",
        "flow": validated["flow"],
        "person_id": validated["person_id"],
        "document_id": did,
        "observation_ids": observation_ids,
        "observations_count": len(observation_ids),
    }


def store_file(files_root: Path, person_id: str, src: Path, occurred_on: str | None) -> tuple[str, str, str]:
    digest = sha256_file(src)
    mime = mimetypes.guess_type(str(src))[0] or "application/octet-stream"

    safe_name = src.name.replace(os.sep, "_")
    year = (occurred_on or "").split("-")[0] if occurred_on else str(dt.date.today().year)
    subdir = Path(person_id) / year
    dest_dir = files_root / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_name = f"{digest[:16]}_{safe_name}"
    dest = dest_dir / dest_name

    if not dest.exists():
        shutil.copy2(src, dest)

    relpath = Path("files") / subdir / dest_name
    return str(relpath), digest, mime


def add_document(
    conn: sqlite3.Connection,
    files_root: Path,
    src: Path,
    person_id: str,
    title: str | None,
    occurred_on: str | None,
) -> str:
    relpath, digest, mime = store_file(files_root, person_id, src, occurred_on)
    existing = conn.execute("SELECT id FROM documents WHERE sha256=?", (digest,)).fetchone()
    if existing:
        return str(existing[0])

    did = str(uuid.uuid4())

    def _op():
        conn.execute(
            """
            INSERT INTO documents(
              id, person_id, title, occurred_on, file_relpath, sha256, mime_type, created_at
            ) VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                did,
                person_id,
                title or src.name,
                occurred_on,
                relpath,
                digest,
                mime,
                iso_now(),
            ),
        )

    _retry_write(_op)
    return did


def add_observation(
    conn: sqlite3.Connection,
    person_id: str,
    source_doc_id: str,
    report_type: str,
    title: str | None,
    observed_on: str | None,
    patient_name: str | None,
    patient_sex: str | None,
    patient_age_text: str | None,
    patient_dob: str | None,
    hospital_name: str | None,
    department_name: str | None,
    doctor_name: str | None,
    specimen_type: str | None,
    accession_no: str | None,
    items: list,
    extra: dict | None,
) -> str:
    oid = str(uuid.uuid4())
    items_json = json.dumps(items, ensure_ascii=False)
    extra_json = json.dumps(extra or {}, ensure_ascii=False)

    def _op():
        conn.execute(
            """
            INSERT INTO observations(
              id, person_id, source_doc_id, report_type, title, observed_on,
              patient_name, patient_sex, patient_age_text, patient_dob,
              hospital_name, department_name, doctor_name, specimen_type,
              accession_no, items_json, extra_json, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                oid,
                person_id,
                source_doc_id,
                report_type,
                title,
                observed_on,
                patient_name,
                patient_sex,
                patient_age_text,
                patient_dob,
                hospital_name,
                department_name,
                doctor_name,
                specimen_type,
                accession_no,
                items_json,
                extra_json,
                iso_now(),
            ),
        )

    _retry_write(_op)
    return oid


def soft_duplicate_candidates(
    conn: sqlite3.Connection,
    person_id: str,
    report_type: str,
    observed_on: str | None,
    accession_no: str | None,
    items: list | None = None,
) -> list[sqlite3.Row]:
    if accession_no:
        cur = conn.execute(
            """
            SELECT * FROM observations
            WHERE person_id=? AND report_type=? AND accession_no=?
            ORDER BY created_at DESC
            """,
            (person_id, report_type, accession_no),
        )
        rows = list(cur.fetchall())
        if rows:
            return rows

    if not observed_on:
        return []

    cur = conn.execute(
        """
        SELECT * FROM observations
        WHERE person_id=? AND report_type=? AND observed_on=?
        ORDER BY created_at DESC
        """,
        (person_id, report_type, observed_on),
    )
    return list(cur.fetchall())


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", help="Archive data root. Defaults to FAMILY_HEALTH_DATA_DIR or ~/.family-health-data")

    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    p_add = sub.add_parser("add-person")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--alias", action="append", default=[])
    p_add.add_argument("--sex")
    p_add.add_argument("--dob")
    p_add.add_argument("--height-cm", type=float)
    p_add.add_argument("--current-weight-kg", type=float)
    p_add.add_argument("--notes")

    sub.add_parser("list-people")

    p_find = sub.add_parser("find-people")
    p_find.add_argument("q")

    p_match = sub.add_parser("match-person")
    p_match.add_argument("--patient-name", required=True)

    p_add_relationship = sub.add_parser("add-relationship")
    p_add_relationship.add_argument("--subject-person-id", required=True)
    p_add_relationship.add_argument("--relation-type", required=True, choices=sorted(SUPPORTED_RELATIONSHIP_TYPES))
    p_add_relationship.add_argument("--object-person-id", required=True)
    p_add_relationship.add_argument("--notes")

    p_list_relationships = sub.add_parser("list-relationships")
    p_list_relationships.add_argument("--person-id")

    p_list_docs = sub.add_parser("list-documents")
    p_list_docs.add_argument("--person-id")

    p_list_obs = sub.add_parser("list-observations")
    p_list_obs.add_argument("--person-id")

    p_doc = sub.add_parser("add-document")
    p_doc.add_argument("file")
    p_doc.add_argument("--person-id", required=True)
    p_doc.add_argument("--title")
    p_doc.add_argument("--occurred-on")

    p_obs = sub.add_parser("add-observation")
    p_obs.add_argument("--person-id", required=True)
    p_obs.add_argument("--source-doc-id", required=True)
    p_obs.add_argument("--report-type", required=True)
    p_obs.add_argument("--title")
    p_obs.add_argument("--observed-on")
    p_obs.add_argument("--patient-name")
    p_obs.add_argument("--patient-sex")
    p_obs.add_argument("--patient-age-text")
    p_obs.add_argument("--patient-dob")
    p_obs.add_argument("--hospital-name")
    p_obs.add_argument("--department-name")
    p_obs.add_argument("--doctor-name")
    p_obs.add_argument("--specimen-type")
    p_obs.add_argument("--accession-no")
    p_obs.add_argument("--items-json", required=True)
    p_obs.add_argument("--extra-json")
    p_obs.add_argument("--check-soft-duplicate", action="store_true")

    p_import = sub.add_parser("import-structured-result")
    p_import.add_argument("--person-id", required=True)
    p_import.add_argument("--file", required=True)
    p_import.add_argument("--report-type", required=True)
    p_import.add_argument("--title")
    p_import.add_argument("--observed-on")
    p_import.add_argument("--patient-name")
    p_import.add_argument("--patient-sex")
    p_import.add_argument("--patient-age-text")
    p_import.add_argument("--patient-dob")
    p_import.add_argument("--hospital-name")
    p_import.add_argument("--department-name")
    p_import.add_argument("--doctor-name")
    p_import.add_argument("--specimen-type")
    p_import.add_argument("--accession-no")
    p_import.add_argument("--items-json", required=True)
    p_import.add_argument("--extra-json")
    p_import.add_argument("--check-soft-duplicate", action="store_true")

    p_gate = sub.add_parser("gate-medical-file")
    p_gate.add_argument("file")

    p_validate_medical = sub.add_parser("validate-medical-archive-result")
    p_validate_medical.add_argument("--json-file", required=True)

    p_resolve_person = sub.add_parser("resolve-medical-archive-result-person")
    p_resolve_person.add_argument("--json-file", required=True)
    p_resolve_person.add_argument("--write-json-file")

    p_assign_person = sub.add_parser("assign-person-to-medical-archive-result")
    p_assign_person.add_argument("--json-file", required=True)
    p_assign_person.add_argument("--person-id", required=True)
    p_assign_person.add_argument("--write-json-file")
    p_assign_person.add_argument("--import", dest="do_import", action="store_true")
    p_assign_person.add_argument("--check-soft-duplicate", action="store_true")

    p_create_person = sub.add_parser("create-person-for-medical-archive-result")
    p_create_person.add_argument("--json-file", required=True)
    p_create_person.add_argument("--name")
    p_create_person.add_argument("--alias", action="append", default=[])
    p_create_person.add_argument("--sex")
    p_create_person.add_argument("--dob")
    p_create_person.add_argument("--height-cm", type=float)
    p_create_person.add_argument("--current-weight-kg", type=float)
    p_create_person.add_argument("--notes")
    p_create_person.add_argument("--write-json-file")
    p_create_person.add_argument("--import", dest="do_import", action="store_true")
    p_create_person.add_argument("--check-soft-duplicate", action="store_true")

    p_process_medical = sub.add_parser("process-medical-archive-result")
    p_process_medical.add_argument("--json-file", required=True)
    p_process_medical.add_argument("--check-soft-duplicate", action="store_true")

    p_import_medical = sub.add_parser("import-medical-archive-result")
    p_import_medical.add_argument("--json-file", required=True)
    p_import_medical.add_argument("--check-soft-duplicate", action="store_true")

    args = ap.parse_args(argv)

    conn: sqlite3.Connection | None = None
    files_root: Path | None = None
    db_commands = {
        "init",
        "add-person",
        "list-people",
        "find-people",
        "match-person",
        "add-relationship",
        "list-relationships",
        "list-documents",
        "list-observations",
        "add-document",
        "add-observation",
        "import-structured-result",
        "resolve-medical-archive-result-person",
        "assign-person-to-medical-archive-result",
        "create-person-for-medical-archive-result",
        "process-medical-archive-result",
        "import-medical-archive-result",
    }

    if args.cmd in db_commands:
        data_root = resolve_data_root(args.data_root)
        db_path, files_root = ensure_data_root(data_root)
        conn = connect(db_path)
        init_db(conn)

    if args.cmd == "init":
        print(f"OK: initialized {db_path}")
        return 0

    if args.cmd == "add-person":
        pid = add_person(
            conn,
            display_name=args.name,
            aliases=args.alias,
            sex=args.sex,
            dob=args.dob,
            height_cm=args.height_cm,
            current_weight_kg=args.current_weight_kg,
            notes=args.notes,
        )
        print(pid)
        return 0

    if args.cmd == "list-people":
        for r in list_people(conn):
            print(f"{r['id']}\t{r['display_name']}\t{r['aliases_json']}")
        return 0

    if args.cmd == "find-people":
        for r in find_people(conn, args.q):
            print(f"{r['id']}\t{r['display_name']}\t{r['aliases_json']}")
        return 0

    if args.cmd == "match-person":
        print(json_dumps(match_person_by_name(conn, args.patient_name)))
        return 0

    if args.cmd == "add-relationship":
        try:
            rid = add_relationship(
                conn,
                subject_person_id=args.subject_person_id,
                relation_type=args.relation_type,
                object_person_id=args.object_person_id,
                notes=args.notes,
            )
        except ValueError as exc:
            return fail(str(exc), code="invalid_relationship")
        print(rid)
        return 0

    if args.cmd == "list-relationships":
        for r in list_relationships(conn, args.person_id):
            print(json.dumps({
                "id": r["id"],
                "subject_person_id": r["subject_person_id"],
                "relation_type": r["relation_type"],
                "object_person_id": r["object_person_id"],
                "notes": r["notes"],
            }, ensure_ascii=False))
        return 0

    if args.cmd == "list-documents":
        for r in list_documents(conn, args.person_id):
            print(json.dumps({
                "id": r["id"],
                "person_id": r["person_id"],
                "title": r["title"],
                "occurred_on": r["occurred_on"],
                "file_relpath": r["file_relpath"],
                "sha256": r["sha256"],
                "mime_type": r["mime_type"],
            }, ensure_ascii=False))
        return 0

    if args.cmd == "list-observations":
        for r in list_observations(conn, args.person_id):
            data = observation_summary(r)
            data["items_count"] = len(json.loads(r["items_json"])) if r["items_json"] else 0
            print(json.dumps(data, ensure_ascii=False))
        return 0

    if args.cmd == "add-document":
        did = add_document(
            conn,
            files_root=files_root,
            src=Path(args.file),
            person_id=args.person_id,
            title=args.title,
            occurred_on=args.occurred_on,
        )
        print(did)
        return 0

    if args.cmd == "gate-medical-file":
        src = Path(args.file)
        if not src.exists():
            return fail(
                f"file does not exist: {src}",
                code="file_missing",
                details={"file": str(src)},
            )
        print(json_dumps(infer_gate_stub(src)))
        return 0

    if args.cmd == "add-observation":
        items = json.loads(args.items_json)
        extra = json.loads(args.extra_json) if args.extra_json else None

        if args.check_soft_duplicate:
            rows = soft_duplicate_candidates(
                conn,
                person_id=args.person_id,
                report_type=args.report_type,
                observed_on=args.observed_on,
                accession_no=args.accession_no,
                items=items,
            )
            if rows:
                print(json.dumps({
                    "status": "suspected_duplicate",
                    "count": len(rows),
                    "existing": [
                        {
                            "summary": observation_summary(r),
                            "items": observation_items(r),
                        }
                        for r in rows
                    ],
                }, ensure_ascii=False))
                return 10

        oid = add_observation(
            conn,
            person_id=args.person_id,
            source_doc_id=args.source_doc_id,
            report_type=args.report_type,
            title=args.title,
            observed_on=args.observed_on,
            patient_name=args.patient_name,
            patient_sex=args.patient_sex,
            patient_age_text=args.patient_age_text,
            patient_dob=args.patient_dob,
            hospital_name=args.hospital_name,
            department_name=args.department_name,
            doctor_name=args.doctor_name,
            specimen_type=args.specimen_type,
            accession_no=args.accession_no,
            items=items,
            extra=extra,
        )
        print(oid)
        return 0

    if args.cmd == "import-structured-result":
        src = Path(args.file)
        did = add_document(
            conn,
            files_root=files_root,
            src=src,
            person_id=args.person_id,
            title=args.title,
            occurred_on=args.observed_on,
        )

        items = json.loads(args.items_json)
        extra = json.loads(args.extra_json) if args.extra_json else None

        if args.check_soft_duplicate:
            rows = soft_duplicate_candidates(
                conn,
                person_id=args.person_id,
                report_type=args.report_type,
                observed_on=args.observed_on,
                accession_no=args.accession_no,
                items=items,
            )
            if rows:
                print(json.dumps({
                    "status": "suspected_duplicate",
                    "document_id": did,
                    "existing": [
                        {
                            "summary": observation_summary(r),
                            "items": observation_items(r),
                        }
                        for r in rows
                    ],
                }, ensure_ascii=False))
                return 10

        oid = add_observation(
            conn,
            person_id=args.person_id,
            source_doc_id=did,
            report_type=args.report_type,
            title=args.title,
            observed_on=args.observed_on,
            patient_name=args.patient_name,
            patient_sex=args.patient_sex,
            patient_age_text=args.patient_age_text,
            patient_dob=args.patient_dob,
            hospital_name=args.hospital_name,
            department_name=args.department_name,
            doctor_name=args.doctor_name,
            specimen_type=args.specimen_type,
            accession_no=args.accession_no,
            items=items,
            extra=extra,
        )
        print(json.dumps({
            "status": "imported",
            "document_id": did,
            "observation_id": oid,
        }, ensure_ascii=False))
        return 0

    if args.cmd == "validate-medical-archive-result":
        try:
            payload = load_json_file(Path(args.json_file))
            validated = validate_extraction_payload(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return fail(
                str(exc),
                code="invalid_extraction_result",
                details={"json_file": args.json_file},
            )
        print(json_dumps({"status": "ok", "validated": validated}))
        return 0

    if args.cmd == "resolve-medical-archive-result-person":
        try:
            payload = load_json_file(Path(args.json_file))
            resolved = resolve_person_match_for_payload(conn, payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return fail(
                str(exc),
                code="invalid_medical_archive_result",
                details={"json_file": args.json_file},
            )

        if args.write_json_file:
            write_json_file(Path(args.write_json_file), resolved)

        person_match = resolved["person_match"]
        status = "resolved" if person_match["status"] == "matched_existing_profile" else "action_required"
        result = {
            "status": status,
            "person_match": person_match,
            "medical_archive_result": resolved,
        }
        if person_match["status"] == "matched_existing_profile" and resolved["person_id"]:
            row = get_person(conn, resolved["person_id"])
            if row:
                result["matched_person"] = person_summary(row)
        elif person_match["status"] == "needs_profile_selection":
            result["candidate_profiles"] = candidate_people_for_match(conn, person_match)
        print(json_dumps(result))
        return 0

    if args.cmd == "assign-person-to-medical-archive-result":
        try:
            payload = load_json_file(Path(args.json_file))
            assigned = assign_person_to_payload(conn, payload, args.person_id)
            if args.write_json_file:
                write_json_file(Path(args.write_json_file), assigned)
            if args.do_import:
                exit_code, result = import_extraction_payload(
                    conn,
                    files_root=files_root,
                    payload=assigned,
                    check_soft_duplicate=args.check_soft_duplicate,
                )
                result["medical_archive_result"] = assigned
                print(json_dumps(result))
                return exit_code
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return fail(
                str(exc),
                code="assign_person_failed",
                details={"json_file": args.json_file, "person_id": args.person_id},
            )

        row = get_person(conn, args.person_id)
        print(json_dumps({
            "status": "person_assigned",
            "person": person_summary(row),
            "medical_archive_result": assigned,
        }))
        return 0

    if args.cmd == "create-person-for-medical-archive-result":
        try:
            payload = load_json_file(Path(args.json_file))
            person_id, assigned = create_person_for_payload(
                conn,
                payload,
                name=args.name,
                aliases=args.alias,
                sex=args.sex,
                dob=args.dob,
                height_cm=args.height_cm,
                current_weight_kg=args.current_weight_kg,
                notes=args.notes,
            )
            if args.write_json_file:
                write_json_file(Path(args.write_json_file), assigned)
            if args.do_import:
                exit_code, result = import_extraction_payload(
                    conn,
                    files_root=files_root,
                    payload=assigned,
                    check_soft_duplicate=args.check_soft_duplicate,
                )
                result["medical_archive_result"] = assigned
                result["created_person_id"] = person_id
                print(json_dumps(result))
                return exit_code
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return fail(
                str(exc),
                code="create_person_failed",
                details={"json_file": args.json_file},
            )

        row = get_person(conn, person_id)
        print(json_dumps({
            "status": "person_created",
            "person": person_summary(row),
            "medical_archive_result": assigned,
        }))
        return 0

    if args.cmd == "import-medical-archive-result":
        try:
            payload = load_json_file(Path(args.json_file))
            exit_code, result = import_extraction_payload(
                conn,
                files_root=files_root,
                payload=payload,
                check_soft_duplicate=args.check_soft_duplicate,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return fail(
                str(exc),
                code="invalid_extraction_result",
                details={"json_file": args.json_file},
            )
        print(json_dumps(result))
        return exit_code

    if args.cmd == "process-medical-archive-result":
        try:
            payload = load_json_file(Path(args.json_file))
            resolved = resolve_person_match_for_payload(conn, payload)
            exit_code, result = import_extraction_payload(
                conn,
                files_root=files_root,
                payload=resolved,
                check_soft_duplicate=args.check_soft_duplicate,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return fail(
                str(exc),
                code="invalid_medical_archive_result",
                details={"json_file": args.json_file},
            )

        result["medical_archive_result"] = resolved
        if result.get("reason") == "person_profile_action_required":
            person_match = result["person_match"]
            result["status"] = "action_required"
            if person_match["status"] == "needs_profile_selection":
                result["candidate_profiles"] = candidate_people_for_match(conn, person_match)
        print(json_dumps(result))
        return exit_code

    raise RuntimeError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
