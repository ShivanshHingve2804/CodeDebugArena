"""Tests for per-agent/per-challenge timing and timeout behavior."""
import json
import sys
import time
from pathlib import Path

import multi_agent_runner as multi


def _challenge(root, name="01_sample"):
    challenge = root / name
    challenge.mkdir()
    (challenge / "buggy.py").write_text("def answer():\n    return 0\n", encoding="utf-8")
    (challenge / "README.md").write_text("# Sample\nFix answer().\n", encoding="utf-8")
    (challenge / "test_challenge.py").write_text(
        "import importlib, os\n"
        "mod = importlib.import_module(os.environ.get('CHALLENGE_TARGET', 'fixed'))\n"
        "def test_answer(): assert mod.answer() == 1\n",
        encoding="utf-8",
    )
    return challenge


def test_agent_completion_time_and_validation_are_recorded(tmp_path):
    challenge = _challenge(tmp_path)
    command = "{} -c \"from pathlib import Path; Path('buggy.py').write_text('def answer():\\n    return 1\\n')\"".format(
        sys.executable
    )
    result = multi.run_one(challenge, "test-agent", command, 120)

    assert result["status"] == "passed"
    assert result["passed"] is True
    assert result["completion_seconds"] is not None
    assert result["completion_seconds"] >= 0
    assert result["validation_seconds"] is not None


def test_agent_timeout_is_120_seconds_by_default():
    assert multi.DEFAULT_TIMEOUT_SECONDS == 120


def test_agent_timeout_is_reported(tmp_path):
    challenge = _challenge(tmp_path)
    command = "{} -c \"import time; time.sleep(2)\"".format(sys.executable)
    result = multi.run_one(challenge, "slow-agent", command, 1)

    assert result["status"] == "timed_out"
    assert result["completion_seconds"] is not None
    assert result["completion_seconds"] < 2


def test_report_has_one_result_per_agent_challenge_pair(tmp_path, monkeypatch):
    challenge = _challenge(tmp_path)
    def fake_run(challenge, agent_name, command_template, timeout):
        return {
            "agent": agent_name, "challenge": challenge.name, "timeout_seconds": timeout,
            "status": "passed", "completion_seconds": 1.25, "validation_seconds": 0.1,
            "passed": True, "return_code": 0, "output_excerpt": "",
        }
    monkeypatch.setattr(multi, "run_one", fake_run)

    report = multi.build_report(
        [("agent-a", "cmd"), ("agent-b", "cmd")], [challenge], timeout=120, concurrency=2
    )

    assert report["summary"]["total_runs"] == 2
    assert len(report["results"]) == 2
    assert {row["agent"] for row in report["results"]} == {"agent-a", "agent-b"}
    assert all(row["completion_seconds"] == 1.25 for row in report["results"])
