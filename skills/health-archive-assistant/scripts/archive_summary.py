#!/usr/bin/env python3
"""Build assistant-side compact summary JSON from archive context and analysis data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CURRENT_DIR.resolve()))

from archive_analysis import ANALYSIS_SCHEMA_VERSION, DOMAIN_REGISTRY, build_analysis_result  # noqa: E402
from archive_patient_context import PATIENT_CONTEXT_SCHEMA_VERSION, build_patient_context  # noqa: E402
from archive_db import connect, init_db, json_dumps, resolve_data_root  # noqa: E402


SUMMARY_SCHEMA_VERSION = "medical-summary-result/v1"


def format_value_text(value, unit: str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float):
        rendered = f"{value:.2f}".rstrip("0").rstrip(".")
    else:
        rendered = str(value)
    return f"{rendered} {unit}".strip() if unit else rendered


def build_trend_highlights(analysis_payload: dict) -> list[dict]:
    highlights = []
    for series in analysis_payload.get("series", []):
        points = [point for point in series.get("points", []) if point.get("value") is not None]
        if not points:
            continue
        latest = points[-1]
        previous = points[-2] if len(points) > 1 else None
        latest_value_text = format_value_text(latest.get("value"), series.get("unit"))
        if previous is None:
            summary_text = f"最近一次{series['label']}记录为 {latest_value_text}。"
        else:
            delta = latest["value"] - previous["value"]
            if abs(delta) < 1e-9:
                trend_text = "与上一次持平"
            elif delta > 0:
                trend_text = "比上一次更高"
            else:
                trend_text = "比上一次更低"
            summary_text = f"最近一次{series['label']}为 {latest_value_text}，{trend_text}。"
        highlights.append(
            {
                "metric_key": series["metric_key"],
                "label": series["label"],
                "summary_text": summary_text,
                "latest_value_text": latest_value_text,
            }
        )
    return highlights


def build_history_highlights(context_payload: dict, limit: int = 5) -> list[dict]:
    highlights = []
    for item in context_payload.get("history_candidates", [])[:limit]:
        observed_on = item.get("observed_on")
        prefix = f"{observed_on} " if observed_on else ""
        highlights.append(
            {
                "label": "长期病史候选",
                "summary_text": f"{prefix}{item.get('summary_text')}",
                "observed_on": observed_on,
            }
        )
    return highlights


def build_key_facts(context_payload: dict) -> list[dict]:
    recent_reports = context_payload.get("recent_reports", [])
    fact_items = [
        {
            "label": "最近报告数",
            "fact_text": f"最近上下文中整理出 {len(recent_reports)} 份近期报告。",
        }
    ]
    if recent_reports:
        latest = recent_reports[0]
        fact_items.append(
            {
                "label": "最近一次报告",
                "fact_text": f"最近一次归档报告为 {latest.get('observed_on') or '未知日期'} 的{latest.get('title') or latest.get('report_type') or '报告'}。",
            }
        )
    return fact_items


def build_summary_result(conn, person_id: str, scope: str, focus_domain: str | None) -> dict:
    context_payload = build_patient_context(conn, person_id, recent_report_limit=12, history_limit=20)
    person = {
        "id": context_payload["person"]["id"],
        "display_name": context_payload["person"]["display_name"],
    }

    trend_highlights = []
    if focus_domain:
        analysis_payload = build_analysis_result(conn, person_id, focus_domain)
        trend_highlights = build_trend_highlights(analysis_payload)
    else:
        for analysis_payload in context_payload.get("recent_trend_data", []):
            trend_highlights.extend(build_trend_highlights(analysis_payload))

    result = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "scope": scope,
        "person": person,
        "focus_domain": focus_domain,
        "key_facts": build_key_facts(context_payload),
        "trend_highlights": trend_highlights,
        "history_highlights": build_history_highlights(context_payload),
        "caution_flags": [
            {
                "type": "archive_incomplete_record",
                "text": "这只是基于已归档资料的总结，不等于完整医院病历。",
            }
        ],
        "source_refs": context_payload.get("source_refs", []),
    }
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", help="Archive data root. Defaults to FAMILY_HEALTH_DATA_DIR or ~/.family-health-data")
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--scope", choices=["person_overview", "domain_overview"], default="person_overview")
    parser.add_argument("--domain", choices=sorted(DOMAIN_REGISTRY))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    try:
        data_root = resolve_data_root(args.data_root)
        db_path = data_root / "archive.db"
        conn = connect(db_path)
        init_db(conn)
        result = build_summary_result(conn, args.person_id, args.scope, args.domain)
    except ValueError as exc:
        print(json_dumps({"status": "error", "error": {"code": "invalid_summary_request", "message": str(exc)}}))
        return 2

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json_dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
