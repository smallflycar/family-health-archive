import json
import shutil
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skills" / "health-archive-manager" / "scripts" / "archive_db.py"
EXTRACT_SCRIPT_PATH = REPO_ROOT / "skills" / "health-archive-manager" / "scripts" / "extract_medical_file.py"
ANALYSIS_SCRIPT_PATH = REPO_ROOT / "skills" / "health-archive-assistant" / "scripts" / "archive_analysis.py"
PATIENT_CONTEXT_SCRIPT_PATH = REPO_ROOT / "skills" / "health-archive-assistant" / "scripts" / "archive_patient_context.py"
SUMMARY_SCRIPT_PATH = REPO_ROOT / "skills" / "health-archive-assistant" / "scripts" / "archive_summary.py"
RENDER_SCRIPT_PATH = REPO_ROOT / "skills" / "health-archive-assistant" / "scripts" / "render_chart_spec.py"


def run_cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["python3", str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit code {proc.returncode}, expected {expected_exit}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def run_extract_cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["python3", str(EXTRACT_SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit code {proc.returncode}, expected {expected_exit}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def run_analysis_cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["python3", str(ANALYSIS_SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit code {proc.returncode}, expected {expected_exit}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def run_patient_context_cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["python3", str(PATIENT_CONTEXT_SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit code {proc.returncode}, expected {expected_exit}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def run_summary_cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["python3", str(SUMMARY_SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit code {proc.returncode}, expected {expected_exit}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def run_render_cli(*args: str, expected_exit: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["python3", str(RENDER_SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != expected_exit:
        raise AssertionError(
            f"unexpected exit code {proc.returncode}, expected {expected_exit}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


class ArchiveDbCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = REPO_ROOT / ".test-tmp" / self.id()
        shutil.rmtree(self.tempdir, ignore_errors=True)
        self.tempdir.mkdir(parents=True, exist_ok=True)
        self.data_root = self.tempdir / "data"
        run_cli("--data-root", str(self.data_root), "init")
        self.person_id = run_cli(
            "--data-root",
            str(self.data_root),
            "add-person",
            "--name",
            "成员A",
        ).stdout.strip()

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def write_json(self, name: str, payload: dict) -> Path:
        path = self.tempdir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_bytes(self, name: str, content: bytes) -> Path:
        path = self.tempdir / name
        path.write_bytes(content)
        return path

    def test_gate_medical_file_stub_detects_supported_pdf_with_medical_filename(self) -> None:
        sample = self.write_bytes("lipid-report.pdf", b"%PDF-1.4 fake content\n")
        proc = run_cli("gate-medical-file", str(sample))
        data = json.loads(proc.stdout)
        self.assertEqual(data["decision"], "accepted_medical_file")
        self.assertEqual(data["source_kind"], "pdf")
        self.assertTrue(data["stub"])

    def test_validate_extraction_result_accepts_image_shape(self) -> None:
        sample = self.write_bytes("lipid-report.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(sample),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {
                "title": "Lipid report",
                "occurred_on": "2026-03-18",
            },
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "Lipid panel",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [
                        {"name": "LDL-C", "value": "4.12", "unit": "mmol/L"}
                    ],
                    "extra": {"source": "unit-test"},
                }
            ],
        }
        payload_path = self.write_json("image-payload.json", payload)
        proc = run_cli("validate-medical-archive-result", "--json-file", str(payload_path))
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["validated"]["flow"], "image_report")
        self.assertEqual(data["validated"]["person_match"]["status"], "matched_existing_profile")
        self.assertEqual(data["validated"]["schema_version"], "medical-archive-result/v1")

    def test_validate_extraction_result_rejects_multi_observation_image_flow(self) -> None:
        sample = self.write_bytes("cbc-report.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(sample),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {},
            "observations": [
                {"report_type": "cbc", "items": []},
                {"report_type": "lipid panel", "items": []},
            ],
        }
        payload_path = self.write_json("invalid-image-payload.json", payload)
        proc = run_cli(
            "validate-medical-archive-result",
            "--json-file",
            str(payload_path),
            expected_exit=2,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error"]["code"], "invalid_extraction_result")

    def test_import_extraction_result_pdf_split_creates_one_document_and_many_observations(self) -> None:
        sample = self.write_bytes("physical-exam-report.pdf", b"%PDF-1.4 fake content\n")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "pdf_split_report",
            "person_id": self.person_id,
            "source_file": str(sample),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "pdf",
                "mime_type": "application/pdf",
            },
            "document": {
                "title": "2026 physical exam",
                "occurred_on": "2026-03-10",
            },
            "observations": [
                {
                    "report_type": "complete blood count",
                    "title": "CBC",
                    "observed_on": "2026-03-10",
                    "patient_name": "成员A",
                    "items": [{"name": "WBC", "value": "5.7", "unit": "10^9/L"}],
                    "extra": {"pdf_section": "lab/cbc"},
                },
                {
                    "report_type": "thyroid ultrasound",
                    "title": "Thyroid ultrasound",
                    "observed_on": "2026-03-10",
                    "patient_name": "成员A",
                    "items": [{"name": "Conclusion", "text": "Follow-up advised"}],
                    "extra": {"pdf_section": "imaging/thyroid"},
                },
            ],
        }
        payload_path = self.write_json("pdf-payload.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "import-medical-archive-result",
            "--json-file",
            str(payload_path),
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "imported")
        self.assertEqual(data["observations_count"], 2)

        docs_proc = run_cli("--data-root", str(self.data_root), "list-documents", "--person-id", self.person_id)
        doc_lines = [line for line in docs_proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(doc_lines), 1)

        obs_proc = run_cli("--data-root", str(self.data_root), "list-observations", "--person-id", self.person_id)
        obs_lines = [line for line in obs_proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(obs_lines), 2)

    def test_import_extraction_result_stops_when_gate_is_not_accepted(self) -> None:
        sample = self.write_bytes("family-photo.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(sample),
            "medical_file_gate": {
                "decision": "needs_manual_review",
                "source_kind": "image",
                "mime_type": "image/png",
                "reject_reasons": ["incomplete_or_unclear_report"],
                "missing_sections": [],
                "quality_flags": [],
                "reupload_advice": "请重新上传完整清晰的原图或原始PDF，确保整张化验单完整可见。",
            },
            "document": {"title": "Family photo"},
            "observations": [
                {
                    "report_type": "unknown",
                    "items": [],
                }
            ],
        }
        payload_path = self.write_json("gated-off.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "import-medical-archive-result",
            "--json-file",
            str(payload_path),
            expected_exit=20,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "not_imported")
        self.assertEqual(data["reason"], "needs_manual_review_before_import")
        self.assertEqual(data["next_action"], "reupload_file")
        self.assertEqual(data["reject_reasons"], ["incomplete_or_unclear_report"])
        self.assertEqual(data["missing_sections"], [])
        self.assertEqual(data["quality_flags"], [])
        self.assertIn("完整清晰", data["reupload_advice"])

    def test_import_extraction_result_stops_when_profile_creation_is_needed(self) -> None:
        sample = self.write_bytes("lipid-report.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "source_file": str(sample),
            "person_match": {
                "status": "needs_profile_creation",
                "extracted_patient_name": "成员A",
                "notes": "No confident existing profile match",
            },
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Lipid report"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "items": [{"name": "LDL-C", "value": "4.12"}],
                    "patient_name": "成员A",
                }
            ],
        }
        payload_path = self.write_json("needs-profile.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "import-medical-archive-result",
            "--json-file",
            str(payload_path),
            expected_exit=21,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "not_imported")
        self.assertEqual(data["reason"], "person_profile_action_required")
        self.assertEqual(data["person_match"]["status"], "needs_profile_creation")

    def test_match_person_prefers_exact_name_and_alias(self) -> None:
        alias_person_id = run_cli(
            "--data-root",
            str(self.data_root),
            "add-person",
            "--name",
            "成员A的母亲",
            "--alias",
            "成员A",
        ).stdout.strip()

        name_match = json.loads(
            run_cli(
                "--data-root",
                str(self.data_root),
                "match-person",
                "--patient-name",
                "成员A",
            ).stdout
        )
        self.assertEqual(name_match["status"], "matched_existing_profile")
        self.assertEqual(name_match["matched_person_id"], self.person_id)

        alias_match = json.loads(
            run_cli(
                "--data-root",
                str(self.data_root),
                "match-person",
                "--patient-name",
                "成员A的母亲",
            ).stdout
        )
        self.assertEqual(alias_match["status"], "matched_existing_profile")
        self.assertEqual(alias_match["matched_person_id"], alias_person_id)

    def test_add_and_list_relationships(self) -> None:
        mother_id = run_cli(
            "--data-root",
            str(self.data_root),
            "add-person",
            "--name",
            "成员A的母亲",
        ).stdout.strip()
        rid = run_cli(
            "--data-root",
            str(self.data_root),
            "add-relationship",
            "--subject-person-id",
            mother_id,
            "--relation-type",
            "mother_of",
            "--object-person-id",
            self.person_id,
        ).stdout.strip()
        self.assertTrue(rid)

        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "list-relationships",
            "--person-id",
            self.person_id,
        )
        lines = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["relation_type"], "mother_of")
        self.assertEqual(lines[0]["subject_person_id"], mother_id)
        self.assertEqual(lines[0]["object_person_id"], self.person_id)

    def test_extract_medical_file_matches_existing_profile_from_patient_name(self) -> None:
        sample = self.write_bytes("lipid-report.png", b"fake image bytes")
        result_payload = {
            "schema_version": "medical-archive-result/v1",
            "source_file": str(sample),
            "flow": "image_report",
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {
                "title": "Lipid report",
                "occurred_on": "2026-03-18",
            },
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "Lipid panel",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [{"name": "LDL-C", "value": "4.12", "unit": "mmol/L"}],
                }
            ],
        }
        result_path = self.write_json("medical-result-existing.json", result_payload)

        proc = run_extract_cli(
            "--data-root",
            str(self.data_root),
            "--file",
            str(sample),
            "--json-file",
            str(result_path),
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["person_id"], self.person_id)
        self.assertEqual(data["person_match"]["status"], "matched_existing_profile")

    def test_extract_medical_file_returns_profile_creation_when_no_match_exists(self) -> None:
        sample = self.write_bytes("cbc-report.png", b"fake image bytes")
        result_payload = {
            "schema_version": "medical-archive-result/v1",
            "source_file": str(sample),
            "flow": "image_report",
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {
                "title": "CBC report",
                "occurred_on": "2026-03-18",
            },
            "observations": [
                {
                    "report_type": "complete blood count",
                    "title": "CBC",
                    "observed_on": "2026-03-18",
                    "patient_name": "未知成员",
                    "items": [{"name": "WBC", "value": "5.7", "unit": "10^9/L"}],
                }
            ],
        }
        result_path = self.write_json("medical-result-new-person.json", result_payload)

        proc = run_extract_cli(
            "--data-root",
            str(self.data_root),
            "--file",
            str(sample),
            "--json-file",
            str(result_path),
        )
        data = json.loads(proc.stdout)
        self.assertIsNone(data["person_id"])
        self.assertEqual(data["person_match"]["status"], "needs_profile_creation")

    def test_resolve_medical_archive_result_person_matches_existing_profile(self) -> None:
        sample = self.write_bytes("lipid-report.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "source_file": str(sample),
            "person_match": {
                "status": "needs_profile_creation",
                "extracted_patient_name": "成员A",
            },
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Lipid report"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "patient_name": "成员A",
                    "items": [{"name": "LDL-C", "value": "4.12"}],
                }
            ],
        }
        payload_path = self.write_json("resolve-existing.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "resolve-medical-archive-result-person",
            "--json-file",
            str(payload_path),
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "resolved")
        self.assertEqual(data["person_match"]["status"], "matched_existing_profile")
        self.assertEqual(data["matched_person"]["id"], self.person_id)

    def test_create_person_for_medical_archive_result_can_import(self) -> None:
        sample = self.write_bytes("new-person-report.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "source_file": str(sample),
            "person_match": {
                "status": "needs_profile_creation",
                "extracted_patient_name": "新成员",
            },
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Glucose report"},
            "observations": [
                {
                    "report_type": "glucose",
                    "patient_name": "新成员",
                    "patient_sex": "女",
                    "items": [{"name": "GLU", "value": "5.8", "unit": "mmol/L"}],
                }
            ],
        }
        payload_path = self.write_json("create-and-import.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "create-person-for-medical-archive-result",
            "--json-file",
            str(payload_path),
            "--import",
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "imported")
        created_person_id = data["created_person_id"]
        self.assertTrue(created_person_id)
        self.assertEqual(data["medical_archive_result"]["person_id"], created_person_id)

        people_proc = run_cli("--data-root", str(self.data_root), "list-people")
        self.assertIn("新成员", people_proc.stdout)

        obs_proc = run_cli("--data-root", str(self.data_root), "list-observations", "--person-id", created_person_id)
        obs_lines = [line for line in obs_proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(obs_lines), 1)

    def test_soft_duplicate_flags_same_person_same_date_same_report_type_without_item_alignment(self) -> None:
        first = self.write_bytes("lipid-report-a.png", b"fake image bytes A")
        second = self.write_bytes("lipid-report-b.png", b"fake image bytes B")

        first_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(first),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Lipid report A", "occurred_on": "2026-03-18"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "Lipid A",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [{"name": "LDL-C", "value": "4.12", "unit": "mmol/L"}],
                }
            ],
        }
        second_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(second),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Lipid report B", "occurred_on": "2026-03-18"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "Lipid B",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [{"name": "HDL-C", "value": "1.11", "unit": "mmol/L"}],
                }
            ],
        }

        first_path = self.write_json("first-duplicate-check.json", first_payload)
        second_path = self.write_json("second-duplicate-check.json", second_payload)

        run_cli(
            "--data-root",
            str(self.data_root),
            "import-medical-archive-result",
            "--json-file",
            str(first_path),
            "--check-soft-duplicate",
        )
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "import-medical-archive-result",
            "--json-file",
            str(second_path),
            "--check-soft-duplicate",
            expected_exit=10,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "suspected_duplicate")
        self.assertEqual(data["duplicates"][0]["report_type"], "lipid panel")
        self.assertEqual(data["duplicates"][0]["existing"][0]["summary"]["person_id"], self.person_id)
        self.assertEqual(data["duplicates"][0]["existing"][0]["items"][0]["name"], "LDL-C")

    def test_process_medical_archive_result_auto_imports_when_match_exists(self) -> None:
        sample = self.write_bytes("process-existing.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "source_file": str(sample),
            "person_match": {
                "status": "needs_profile_creation",
                "extracted_patient_name": "成员A",
            },
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Process import"},
            "observations": [
                {
                    "report_type": "cbc",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [{"name": "WBC", "value": "5.7"}],
                }
            ],
        }
        payload_path = self.write_json("process-existing.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "process-medical-archive-result",
            "--json-file",
            str(payload_path),
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "imported")
        self.assertEqual(data["medical_archive_result"]["person_id"], self.person_id)

    def test_process_medical_archive_result_returns_action_required_for_new_person(self) -> None:
        sample = self.write_bytes("process-new-person.png", b"fake image bytes")
        payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "source_file": str(sample),
            "person_match": {
                "status": "needs_profile_creation",
                "extracted_patient_name": "全新成员",
            },
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Need person"},
            "observations": [
                {
                    "report_type": "cbc",
                    "observed_on": "2026-03-18",
                    "patient_name": "全新成员",
                    "items": [{"name": "WBC", "value": "5.7"}],
                }
            ],
        }
        payload_path = self.write_json("process-new-person.json", payload)
        proc = run_cli(
            "--data-root",
            str(self.data_root),
            "process-medical-archive-result",
            "--json-file",
            str(payload_path),
            expected_exit=21,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["status"], "action_required")
        self.assertEqual(data["reason"], "person_profile_action_required")
        self.assertEqual(data["next_action"], "resolve_person_profile")

    def test_archive_analysis_extracts_lipid_series(self) -> None:
        first = self.write_bytes("analysis-lipid-a.png", b"fake image bytes A")
        second = self.write_bytes("analysis-lipid-b.png", b"fake image bytes B")

        first_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(first),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Lipid report 1", "occurred_on": "2026-03-01"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "血脂检验",
                    "observed_on": "2026-03-01",
                    "patient_name": "成员A",
                    "items": [
                        {"name": "低密度脂蛋白胆固醇", "value": "3.80", "unit": "mmol/L"},
                        {"name": "总胆固醇", "value": "5.90", "unit": "mmol/L"},
                    ],
                }
            ],
        }
        second_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(second),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "Lipid report 2", "occurred_on": "2026-03-18"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "血脂检验",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [
                        {"name": "LDL-C", "value": "4.12", "unit": "mmol/L", "flag": "↑"},
                        {"name": "TG", "value": "1.80", "unit": "mmol/L"},
                    ],
                }
            ],
        }

        first_path = self.write_json("analysis-first.json", first_payload)
        second_path = self.write_json("analysis-second.json", second_payload)
        run_cli("--data-root", str(self.data_root), "import-medical-archive-result", "--json-file", str(first_path))
        run_cli("--data-root", str(self.data_root), "import-medical-archive-result", "--json-file", str(second_path))

        proc = run_analysis_cli(
            "--data-root",
            str(self.data_root),
            "--person-id",
            self.person_id,
            "--domain",
            "lipids",
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema_version"], "medical-analysis-result/v1")
        self.assertEqual(data["domain"], "lipids")
        self.assertEqual(data["person"]["id"], self.person_id)
        metric_keys = [series["metric_key"] for series in data["series"]]
        self.assertIn("ldl_c", metric_keys)
        self.assertIn("tc", metric_keys)
        self.assertIn("tg", metric_keys)
        ldl_series = next(series for series in data["series"] if series["metric_key"] == "ldl_c")
        self.assertEqual(len(ldl_series["points"]), 2)
        self.assertEqual(ldl_series["points"][0]["date"], "2026-03-01")
        self.assertEqual(ldl_series["points"][1]["date"], "2026-03-18")

    def test_patient_context_collects_recent_reports_trends_and_history_candidates(self) -> None:
        old_report = self.write_bytes("old-gastric-report.png", b"fake old report")
        new_report = self.write_bytes("new-lipid-report.png", b"fake new report")

        old_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(old_report),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "胃镜报告", "occurred_on": "2014-06-03"},
            "observations": [
                {
                    "report_type": "gastroscopy",
                    "title": "胃镜检查",
                    "observed_on": "2014-06-03",
                    "patient_name": "成员A",
                    "items": [
                        {"name": "检查结论", "text": "胃溃疡，建议随访治疗"}
                    ],
                }
            ],
        }
        new_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(new_report),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "血脂报告", "occurred_on": "2026-03-18"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "血脂检验",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [
                        {"name": "LDL-C", "value": "4.12", "unit": "mmol/L", "flag": "↑"}
                    ],
                }
            ],
        }

        old_path = self.write_json("patient-context-old.json", old_payload)
        new_path = self.write_json("patient-context-new.json", new_payload)
        run_cli("--data-root", str(self.data_root), "import-medical-archive-result", "--json-file", str(old_path))
        run_cli("--data-root", str(self.data_root), "import-medical-archive-result", "--json-file", str(new_path))

        proc = run_patient_context_cli(
            "--data-root",
            str(self.data_root),
            "--person-id",
            self.person_id,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema_version"], "patient-context-result/v1")
        self.assertEqual(data["person"]["id"], self.person_id)
        self.assertGreaterEqual(len(data["recent_reports"]), 2)
        self.assertTrue(any(entry["domain"] == "lipids" for entry in data["recent_trend_data"]))
        self.assertTrue(any("胃溃疡" in entry["summary_text"] for entry in data["history_candidates"]))
        self.assertTrue(any(ref["report_type"] == "gastroscopy" for ref in data["source_refs"]))

    def test_archive_summary_combines_trend_and_history_highlights(self) -> None:
        old_report = self.write_bytes("summary-old-gastric.png", b"old report")
        new_report = self.write_bytes("summary-new-lipid.png", b"new report")

        old_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(old_report),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "胃镜报告", "occurred_on": "2014-06-03"},
            "observations": [
                {
                    "report_type": "gastroscopy",
                    "title": "胃镜检查",
                    "observed_on": "2014-06-03",
                    "patient_name": "成员A",
                    "items": [{"name": "检查结论", "text": "胃溃疡，建议复查"}],
                }
            ],
        }
        new_payload = {
            "schema_version": "medical-archive-result/v1",
            "flow": "image_report",
            "person_id": self.person_id,
            "source_file": str(new_report),
            "medical_file_gate": {
                "decision": "accepted_medical_file",
                "source_kind": "image",
                "mime_type": "image/png",
            },
            "document": {"title": "血脂报告", "occurred_on": "2026-03-18"},
            "observations": [
                {
                    "report_type": "lipid panel",
                    "title": "血脂检验",
                    "observed_on": "2026-03-18",
                    "patient_name": "成员A",
                    "items": [{"name": "LDL-C", "value": "4.12", "unit": "mmol/L", "flag": "↑"}],
                }
            ],
        }
        old_path = self.write_json("summary-old.json", old_payload)
        new_path = self.write_json("summary-new.json", new_payload)
        run_cli("--data-root", str(self.data_root), "import-medical-archive-result", "--json-file", str(old_path))
        run_cli("--data-root", str(self.data_root), "import-medical-archive-result", "--json-file", str(new_path))

        proc = run_summary_cli(
            "--data-root",
            str(self.data_root),
            "--person-id",
            self.person_id,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(data["schema_version"], "medical-summary-result/v1")
        self.assertEqual(data["scope"], "person_overview")
        self.assertTrue(any("最近一次归档报告" in item["fact_text"] for item in data["key_facts"]))
        self.assertTrue(any(item["metric_key"] == "ldl_c" for item in data["trend_highlights"]))
        self.assertTrue(any("胃溃疡" in item["summary_text"] for item in data["history_highlights"]))

    def test_render_chart_spec_outputs_html_card(self) -> None:
        chart_spec = {
            "schema_version": "chart-spec/v1",
            "chart_type": "single_metric_trend_line",
            "title": "低密度脂蛋白胆固醇趋势",
            "subtitle": "更适合观察血脂风险变化",
            "series": [
                {
                    "metric_key": "ldl_c",
                    "label": "低密度脂蛋白胆固醇",
                    "unit": "mmol/L",
                    "points": [
                        {"date": "2026-03-01", "value": 3.8, "label": "3.80"},
                        {"date": "2026-03-18", "value": 4.12, "label": "4.12"},
                    ],
                }
            ],
            "reference_bands": [
                {"label": "建议上限", "upper": 3.4, "color_token": "range_caution"}
            ],
            "latest_supporting_facts": [
                {"label": "最近一次总胆固醇", "value_text": "5.90 mmol/L"}
            ],
        }
        json_path = self.write_json("chart-spec.json", chart_spec)
        html_path = self.tempdir / "chart-card.html"
        run_render_cli("--json-file", str(json_path), "--output-html", str(html_path))
        html_text = html_path.read_text(encoding="utf-8")
        self.assertIn("低密度脂蛋白胆固醇趋势", html_text)
        self.assertIn("健康趋势卡", html_text)


if __name__ == "__main__":
    unittest.main()
