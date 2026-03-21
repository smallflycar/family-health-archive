#!/usr/bin/env python3
"""Build a readable patient-context JSON from the local health archive."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
MANAGER_SCRIPTS_DIR = CURRENT_DIR.parents[1] / "health-archive-manager" / "scripts"
sys.path.insert(0, str(MANAGER_SCRIPTS_DIR.resolve()))
sys.path.insert(0, str(CURRENT_DIR.resolve()))

from archive_db import connect, init_db, json_dumps, resolve_data_root  # noqa: E402
from archive_analysis import DOMAIN_REGISTRY, build_analysis_result, fetch_person  # noqa: E402


PATIENT_CONTEXT_SCHEMA_VERSION = "patient-context-result/v1"
DEFAULT_TREND_DOMAINS = ["lipids", "glucose", "blood_pressure", "weight"]


def fetch_observations_with_docs(conn, person_id: str):
    cur = conn.execute(
        """
        SELECT o.*, d.file_relpath
        FROM observations o
        LEFT JOIN documents d ON d.id = o.source_doc_id
        WHERE o.person_id=?
        ORDER BY COALESCE(o.observed_on, '') DESC, o.created_at DESC
        """,
        (person_id,),
    )
    return list(cur.fetchall())


def recent_reports(observations, limit: int) -> list[dict]:
    result = []
    for row in observations[:limit]:
        result.append(
            {
                "observation_id": row["id"],
                "observed_on": row["observed_on"],
                "report_type": row["report_type"],
                "title": row["title"],
                "hospital_name": row["hospital_name"],
                "patient_name": row["patient_name"],
                "source_doc_id": row["source_doc_id"],
            }
        )
    return result


def source_refs(observations) -> list[dict]:
    refs = []
    seen = set()
    for row in observations:
        key = row["id"]
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            {
                "observation_id": row["id"],
                "source_doc_id": row["source_doc_id"],
                "observed_on": row["observed_on"],
                "report_type": row["report_type"],
                "title": row["title"],
                "file_relpath": row["file_relpath"],
            }
        )
    return refs


def summarize_item_text(item: dict) -> str | None:
    name = item.get("name")
    text = item.get("text")
    value = item.get("value")
    unit = item.get("unit")
    if isinstance(text, str) and text.strip():
        return f"{name}: {text}".strip()
    if value is not None and isinstance(name, str):
        suffix = f" {unit}" if unit else ""
        return f"{name}: {value}{suffix}".strip()
    return None


def history_candidates(observations, limit: int) -> list[dict]:
    candidates = []
    seen = set()
    diagnostic_keywords = (
        "ulcer",
        "结节",
        "胃炎",
        "胃溃疡",
        "息肉",
        "囊肿",
        "结石",
        "异常",
        "诊断",
        "印象",
        "建议",
        "随访",
        "病变",
        "穿孔",
        "炎",
        "增生",
        "钙化",
        "肿瘤",
    )

    for row in observations:
        try:
            items = json.loads(row["items_json"] or "[]")
        except json.JSONDecodeError:
            items = []

        report_text = " ".join(
            str(part)
            for part in (row["report_type"], row["title"], row["hospital_name"])
            if part
        ).casefold()

        picked_text = None
        category = "report_history"
        for item in items:
            if not isinstance(item, dict):
                continue
            candidate_text = summarize_item_text(item)
            searchable = " ".join(
                str(part) for part in (item.get("name"), item.get("text"), item.get("value")) if part is not None
            ).casefold()
            if candidate_text and any(keyword in searchable or keyword in report_text for keyword in diagnostic_keywords):
                picked_text = candidate_text
                category = "text_history_candidate"
                break

        if not picked_text and any(keyword in report_text for keyword in diagnostic_keywords):
            picked_text = row["title"] or row["report_type"]

        if not picked_text:
            continue

        dedupe_key = (row["observed_on"], row["report_type"], picked_text)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        candidates.append(
            {
                "category": category,
                "observed_on": row["observed_on"],
                "report_type": row["report_type"],
                "title": row["title"],
                "summary_text": picked_text,
                "source_observation_id": row["id"],
                "source_doc_id": row["source_doc_id"],
            }
        )
        if len(candidates) >= limit:
            break

    return candidates


def recent_trend_data(conn, person_id: str) -> list[dict]:
    result = []
    for domain in DEFAULT_TREND_DOMAINS:
        if domain not in DOMAIN_REGISTRY:
            continue
        analysis = build_analysis_result(conn, person_id, domain)
        if analysis["series"]:
            result.append(analysis)
    return result


def build_patient_context(conn, person_id: str, *, recent_report_limit: int, history_limit: int) -> dict:
    person = fetch_person(conn, person_id)
    observations = fetch_observations_with_docs(conn, person_id)
    return {
        "schema_version": PATIENT_CONTEXT_SCHEMA_VERSION,
        "person": person,
        "recent_reports": recent_reports(observations, recent_report_limit),
        "recent_trend_data": recent_trend_data(conn, person_id),
        "history_candidates": history_candidates(observations, history_limit),
        "source_refs": source_refs(observations),
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", help="Archive data root. Defaults to FAMILY_HEALTH_DATA_DIR or ~/.family-health-data")
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--recent-report-limit", type=int, default=12)
    parser.add_argument("--history-limit", type=int, default=20)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    try:
        data_root = resolve_data_root(args.data_root)
        db_path = data_root / "archive.db"
        conn = connect(db_path)
        init_db(conn)
        result = build_patient_context(
            conn,
            args.person_id,
            recent_report_limit=args.recent_report_limit,
            history_limit=args.history_limit,
        )
    except ValueError as exc:
        print(json_dumps({"status": "error", "error": {"code": "invalid_patient_context_request", "message": str(exc)}}))
        return 2

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json_dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
