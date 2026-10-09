"""Regression tests for machine-readable benchmark reports."""
import json

import report


def _challenge(root, name, *files):
    directory = root / name
    directory.mkdir()
    for filename in files:
        (directory / filename).write_text("# fixture\n", encoding="utf-8")
    return directory


def test_report_marks_missing_challenge_files_invalid(tmp_path):
    challenge = _challenge(tmp_path, "01_incomplete", "buggy.py")
    result = report.build_report([challenge])

    assert result["summary"]["total"] == 1
    assert result["summary"]["invalid"] == 1
    assert result["challenges"][0]["valid"] is False
    assert "fixed.py" in result["challenges"][0]["issues"][0]


def test_report_accepts_expected_buggy_failure_and_fixed_pass(tmp_path, monkeypatch):
    challenge = _challenge(
        tmp_path, "01_sample", "buggy.py", "fixed.py", "test_challenge.py"
    )
    monkeypatch.setattr(
        report.runner,
        "_run_challenge_tests",
        lambda challenge, target: (
            (1, False, "FAILED test.py::test_case\n1 failed") if target == "buggy"
            else (0, False, "2 passed")
        ),
    )

    result = report.build_report([challenge])
    item = result["challenges"][0]

    assert item["valid"] is True
    assert item["buggy"]["status"] == "failed_tests"
    assert item["fixed"]["status"] == "passed"
    assert result["summary"]["valid"] == 1


def test_report_rejects_buggy_collection_error(tmp_path, monkeypatch):
    challenge = _challenge(
        tmp_path, "01_sample", "buggy.py", "fixed.py", "test_challenge.py"
    )
    monkeypatch.setattr(
        report.runner,
        "_run_challenge_tests",
        lambda challenge, target: (
            (2, False, "ERROR collecting test.py\nModuleNotFoundError: missing")
            if target == "buggy" else (0, False, "2 passed")
        ),
    )

    result = report.build_report([challenge])
    assert result["challenges"][0]["valid"] is False
    assert result["challenges"][0]["buggy"]["status"] == "runner_error"


def test_report_can_be_written_as_valid_json(tmp_path, monkeypatch):
    challenge = _challenge(
        tmp_path, "01_sample", "buggy.py", "fixed.py", "test_challenge.py"
    )
    monkeypatch.setattr(report, "build_report", lambda: {
        "schema_version": "1.0",
        "summary": {"total": 1, "valid": 1, "invalid": 0},
        "challenges": [],
    })
    destination = tmp_path / "reports" / "validation.json"

    assert report.main(["--output", str(destination), "--pretty"]) == 0
    parsed = json.loads(destination.read_text(encoding="utf-8"))
    assert parsed["summary"]["valid"] == 1
