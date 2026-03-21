#!/usr/bin/env python3
"""Extract assistant-side analysis JSON from the local health archive."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

MANAGER_SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".." / "health-archive-manager" / "scripts"
sys.path.insert(0, str(MANAGER_SCRIPTS_DIR.resolve()))

from archive_db import connect, init_db, json_dumps, resolve_data_root  # noqa: E402


ANALYSIS_SCHEMA_VERSION = "medical-analysis-result/v1"

DOMAIN_REGISTRY = {
    "lipids": {
        "metric_labels": {
            "tc": "总胆固醇",
            "ldl_c": "低密度脂蛋白胆固醇",
            "hdl_c": "高密度脂蛋白胆固醇",
            "tg": "甘油三酯",
        },
        "aliases": {
            "总胆固醇": "tc",
            "胆固醇总量": "tc",
            "tc": "tc",
            "cholesterol": "tc",
            "低密度脂蛋白胆固醇": "ldl_c",
            "低密度脂蛋白": "ldl_c",
            "ldl-c": "ldl_c",
            "ldlc": "ldl_c",
            "高密度脂蛋白胆固醇": "hdl_c",
            "高密度脂蛋白": "hdl_c",
            "hdl-c": "hdl_c",
            "hdlc": "hdl_c",
            "甘油三酯": "tg",
            "三酰甘油": "tg",
            "tg": "tg",
            "triglyceride": "tg",
        },
    },
    "glucose": {
        "metric_labels": {
            "fasting_glucose": "空腹血糖",
            "postprandial_glucose": "餐后血糖",
            "hba1c": "糖化血红蛋白",
        },
        "aliases": {
            "空腹血糖": "fasting_glucose",
            "葡萄糖": "fasting_glucose",
            "glucose": "fasting_glucose",
            "fpg": "fasting_glucose",
            "餐后血糖": "postprandial_glucose",
            "2h餐后血糖": "postprandial_glucose",
            "糖化血红蛋白": "hba1c",
            "hba1c": "hba1c",
        },
    },
    "blood_pressure": {
        "metric_labels": {
            "sbp": "收缩压",
            "dbp": "舒张压",
        },
        "aliases": {
            "收缩压": "sbp",
            "高压": "sbp",
            "systolic": "sbp",
            "舒张压": "dbp",
            "低压": "dbp",
            "diastolic": "dbp",
        },
    },
    "weight": {
        "metric_labels": {
            "weight_kg": "体重",
        },
        "aliases": {
            "体重": "weight_kg",
            "weight": "weight_kg",
        },
    },
}


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    lowered = value.casefold()
    lowered = re.sub(r"[\s_\-()/]+", "", lowered)
    return lowered


NORMALIZED_ALIAS_LOOKUP = {
    domain: {normalize_name(alias): metric_key for alias, metric_key in config["aliases"].items()}
    for domain, config in DOMAIN_REGISTRY.items()
}


def parse_numeric_value(raw_value) -> float | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    if not isinstance(raw_value, str):
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", raw_value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def fetch_person(conn, person_id: str):
    row = conn.execute("SELECT * FROM people WHERE id=?", (person_id,)).fetchone()
    if row is None:
        raise ValueError(f"person_id does not exist: {person_id}")
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
        "height_cm": row["height_cm"],
        "current_weight_kg": row["current_weight_kg"],
    }


def fetch_observations(conn, person_id: str):
    cur = conn.execute(
        """
        SELECT o.*, d.file_relpath
        FROM observations o
        LEFT JOIN documents d ON d.id = o.source_doc_id
        WHERE o.person_id=?
        ORDER BY o.observed_on ASC, o.created_at ASC
        """,
        (person_id,),
    )
    return list(cur.fetchall())


def build_domain_series(observations, domain: str) -> tuple[list[dict], int]:
    config = DOMAIN_REGISTRY[domain]
    alias_lookup = NORMALIZED_ALIAS_LOOKUP[domain]
    points_by_metric: dict[str, list[dict]] = {}
    used_observation_ids: set[str] = set()

    for row in observations:
        try:
            items = json.loads(row["items_json"] or "[]")
        except json.JSONDecodeError:
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            metric_key = alias_lookup.get(normalize_name(item.get("name")))
            if not metric_key:
                continue
            points_by_metric.setdefault(metric_key, []).append(
                {
                    "date": row["observed_on"],
                    "value": parse_numeric_value(item.get("value")),
                    "raw_value": item.get("value") if item.get("value") is not None else item.get("text"),
                    "reference_range": item.get("reference_range"),
                    "flag": item.get("flag"),
                    "source_observation_id": row["id"],
                    "source_report_type": row["report_type"],
                    "source_title": row["title"],
                    "source_file_relpath": row["file_relpath"],
                }
            )
            used_observation_ids.add(row["id"])

    if domain == "weight":
        latest_person_weight = None
        for row in observations:
            pass
        # Fall back to profile-level current weight when no observation items exist.
        if not points_by_metric:
            # Weight has no observation history yet; caller still gets an empty series.
            pass

    series = []
    for metric_key, points in points_by_metric.items():
        unit = next((point.get("unit") for point in []), None)
        inferred_unit = None
        for row in observations:
            try:
                items = json.loads(row["items_json"] or "[]")
            except json.JSONDecodeError:
                items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if alias_lookup.get(normalize_name(item.get("name"))) == metric_key and item.get("unit"):
                    inferred_unit = item.get("unit")
                    break
            if inferred_unit:
                break
        points.sort(key=lambda point: ((point["date"] or ""), point["source_observation_id"]))
        series.append(
            {
                "metric_key": metric_key,
                "label": config["metric_labels"].get(metric_key, metric_key),
                "unit": inferred_unit,
                "points": points,
            }
        )

    series.sort(key=lambda item: item["metric_key"])
    return series, len(used_observation_ids)


def build_analysis_result(conn, person_id: str, domain: str) -> dict:
    if domain not in DOMAIN_REGISTRY:
        raise ValueError(f"domain must be one of: {', '.join(sorted(DOMAIN_REGISTRY))}")

    person = fetch_person(conn, person_id)
    observations = fetch_observations(conn, person_id)
    series, observation_count = build_domain_series(observations, domain)

    if domain == "weight" and not series and person.get("current_weight_kg") is not None:
        series = [
            {
                "metric_key": "weight_kg",
                "label": "体重",
                "unit": "kg",
                "points": [
                    {
                        "date": None,
                        "value": float(person["current_weight_kg"]),
                        "raw_value": str(person["current_weight_kg"]),
                        "reference_range": None,
                        "flag": None,
                        "source_observation_id": None,
                        "source_report_type": "profile",
                        "source_title": "current_weight_kg",
                        "source_file_relpath": None,
                    }
                ],
            }
        ]

    return {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "domain": domain,
        "person": person,
        "observation_count": observation_count,
        "series": series,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", help="Archive data root. Defaults to FAMILY_HEALTH_DATA_DIR or ~/.family-health-data")
    parser.add_argument("--person-id", required=True)
    parser.add_argument("--domain", required=True, choices=sorted(DOMAIN_REGISTRY))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    try:
        data_root = resolve_data_root(args.data_root)
        db_path = data_root / "archive.db"
        conn = connect(db_path)
        init_db(conn)
        result = build_analysis_result(conn, args.person_id, args.domain)
    except ValueError as exc:
        print(json_dumps({"status": "error", "error": {"code": "invalid_analysis_request", "message": str(exc)}}))
        return 2

    if args.pretty:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json_dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
